import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { testApi, ApiError } from '@/api/client'
import { useSessionRestore } from '@/composables/useSessionRestore'
import type { AnswerValue, DimensionScore, QuestionResponse, ResultResponse } from '@/types/api'

/**
 * 测试会话 store
 * 负责：创建会话、推进题目、提交答案、获取结果
 */
export const useTestStore = defineStore('test', () => {
  // 会话元数据
  const sessionId = ref<string | null>(null)
  const total = ref(0)
  const currentIndex = ref(0)
  const currentQuestion = ref<QuestionResponse | null>(null)
  const answers = ref<Record<string, AnswerValue>>({})
  const questionStartTime = ref<number>(0)

  // 结果
  const result = ref<ResultResponse | null>(null)

  // UI 状态
  const loading = ref(false)
  const error = ref<string | null>(null)
  const finished = ref(false)

  const progress = computed(() => {
    if (total.value === 0) return 0
    return Math.round((currentIndex.value / total.value) * 100)
  })

  const answeredCount = computed(() => Object.keys(answers.value).length)

  function reset() {
    sessionId.value = null
    total.value = 0
    currentIndex.value = 0
    currentQuestion.value = null
    answers.value = {}
    result.value = null
    loading.value = false
    error.value = null
    finished.value = false
  }

  /**
   * 注水：把外部状态（localStorage / 路由参数）灌进 store。
   * 用于刷新页面后从 useSessionRestore 恢复进度。
   * 灌完之后会自动拉取下一题 + 拉取结果（如果已完成）。
   */
  async function hydrate(payload: { sessionId: string; total: number }) {
    sessionId.value = payload.sessionId
    total.value = payload.total
    loading.value = true
    try {
      // 并行拉：当前题 + 结果（如果已答完，结果会先返回）
      const [q, r] = await Promise.allSettled([
        testApi.nextQuestion(payload.sessionId),
        testApi.getResult(payload.sessionId),
      ])
      if (q.status === 'fulfilled') {
        currentQuestion.value = q.value
        currentIndex.value = q.value.index
        questionStartTime.value = Date.now()
      } else {
        // 拉不到题 = 会话已完成
        finished.value = true
      }
      if (r.status === 'fulfilled') {
        result.value = r.value
        if (r.value.completed) finished.value = true
      }
    } finally {
      loading.value = false
    }
  }

  async function startSession(length = 50) {
    reset()
    loading.value = true
    error.value = null
    try {
      const session = await testApi.createSession({ length })
      sessionId.value = session.session_id
      total.value = session.question_count
      await loadNextQuestion()
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : '创建测试会话失败，请检查后端服务'
    } finally {
      loading.value = false
    }
  }

  async function loadNextQuestion() {
    if (!sessionId.value) return
    loading.value = true
    error.value = null
    try {
      currentQuestion.value = await testApi.nextQuestion(sessionId.value)
      currentIndex.value = currentQuestion.value.index
      questionStartTime.value = Date.now()
    } catch (e) {
      const err = e as ApiError
      // 409 表示已经答完
      if (err.status === 409) {
        finished.value = true
        await fetchResult()
      } else {
        error.value = err.message || '获取题目失败'
      }
    } finally {
      loading.value = false
    }
  }

  async function submitAnswer(answer: AnswerValue) {
    if (!currentQuestion.value || !sessionId.value) return
    const q = currentQuestion.value
    const duration = Math.max(0, Math.round((Date.now() - questionStartTime.value) / 1000))
    loading.value = true
    error.value = null
    try {
      const resp = await testApi.submitAnswer(sessionId.value, {
        question_id: q.question_id,
        answer,
        duration,
      })
      answers.value[q.question_id] = answer
      if (resp.completed) {
        finished.value = true
        await fetchResult()
      } else {
        await loadNextQuestion()
      }
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : '提交答案失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchResult() {
    if (!sessionId.value) return
    loading.value = true
    error.value = null
    try {
      result.value = await testApi.getResult(sessionId.value)
      // 缓存结果到 sessionStorage，刷新结果页时无需后端即可恢复
      const { persistResult, persist } = useSessionRestore()
      persistResult(sessionId.value, result.value)
      persist(sessionId.value, total.value, true)
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : '获取结果失败'
    } finally {
      loading.value = false
    }
  }

  /** 从缓存的 sessionStorage 直接恢复结果（无需后端 API，用于刷新结果页）。 */
  function restoreFromCache(sid: string, cachedResult: ResultResponse) {
    sessionId.value = sid
    total.value = cachedResult.total
    result.value = cachedResult
    finished.value = true
  }

  // 用于结果页：稳定排序的维度列表
  const sortedDimensions = computed<DimensionScore[]>(() => {
    if (!result.value) return []
    return Object.values(result.value.dimensions).sort((a, b) => b.score - a.score)
  })

  return {
    sessionId,
    total,
    currentIndex,
    currentQuestion,
    answers,
    result,
    loading,
    error,
    finished,
    progress,
    answeredCount,
    sortedDimensions,
    startSession,
    loadNextQuestion,
    submitAnswer,
    fetchResult,
    hydrate,
    restoreFromCache,
    reset,
  }
})
