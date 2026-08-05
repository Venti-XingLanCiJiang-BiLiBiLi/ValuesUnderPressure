import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { testApi, ApiError } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import { useProgressStore } from '@/stores/progress'
import { useAnswerStore } from '@/stores/answers'
import { useResultStore } from '@/stores/result'
import type { AnswerValue, ResultResponse } from '@/types/api'

/**
 * 测试会话 store —— 组合门面（#18）
 * ============================================================================
 * 职责拆分后，本 store 仅做「编排」，不再直接持有具体状态：
 * - session  → stores/session.ts   （会话元数据）
 * - progress → stores/progress.ts  （题目进度与导航）
 * - answers  → stores/answers.ts   （答案与历史）
 * - result   → stores/result.ts    （结果与缓存）
 *
 * 保留统一入口，对外 API 与拆分前完全一致，视图层无需改动；
 * 具体状态与请求逻辑已下沉到各单一职责 store，便于单独测试。
 * ============================================================================
 */

export const useTestStore = defineStore('test', () => {
  const session = useSessionStore()
  const progress = useProgressStore()
  const answers = useAnswerStore()
  const result = useResultStore()

  // ---- 兼容字段：转发到子 store ----
  const sessionId = computed(() => session.sessionId)
  const total = computed(() => session.total)
  const currentIndex = computed(() => progress.currentIndex)
  const currentQuestion = computed(() => progress.currentQuestion)
  const answersMap = computed(() => answers.answers)
  const seenQuestions = computed(() => progress.seenQuestions)
  const progressIndex = computed(() => progress.progressIndex)
  const canGoBack = computed(() => progress.canGoBack)
  const canGoNext = computed(() => progress.canGoNext)
  const resultValue = computed(() => result.result)
  const finished = computed(() => result.finished)

  const progressPercent = computed(() => {
    if (total.value === 0) return 0
    return Math.round((currentIndex.value / total.value) * 100)
  })
  const answeredCount = computed(() => answers.answeredCount)

  // ---- 编排层自己的 UI 状态 ----
  // #20：细化加载状态，区分「创建 / 取题 / 提交 / 拉结果」
  const loadingState = ref<
    'idle' | 'creating' | 'fetching' | 'submitting' | 'result'
  >('idle')
  /** 兼容旧字段：是否处于任意加载中。 */
  const loading = computed(() => loadingState.value !== 'idle')
  /** #20：语义化的加载判定。 */
  const isLoading = computed(() => loadingState.value !== 'idle')
  const error = ref<string | null>(null)

  function reset() {
    // 先清除当前会话的本地缓存（答案 + 题目浏览位置），按 sessionId 定向清除
    if (session.sessionId) {
      answers.clearPersisted(session.sessionId)
      progress.clearPersisted(session.sessionId)
    }
    session.reset()
    progress.reset()
    answers.reset()
    result.reset()
    loadingState.value = 'idle'
    error.value = null
  }

  /** 创建新会话并加载第一题。 */
  async function startSession(length = 50) {
    reset()
    loadingState.value = 'creating'
    error.value = null
    try {
      await session.create(length)
      await loadNextQuestion()
    } catch (e) {
      error.value =
        e instanceof ApiError ? e.message : '创建测试会话失败，请检查后端服务'
    } finally {
      loadingState.value = 'idle'
    }
  }

  /**
   * 注水：把外部状态（localStorage / 路由参数）灌进各子 store。
   * 灌完之后自动拉取下一题 + 拉取结果（如果已完成）。
   */
  async function hydrate(payload: { sessionId: string; total: number }) {
    session.restore(payload.sessionId, payload.total)
    // 恢复已提交答案与题目浏览位置的本地缓存（刷新后返回上一题可看到选中态）
    answers.restoreFromStorage(payload.sessionId)
    progress.restoreFromStorage(payload.sessionId)
    loadingState.value = 'fetching'
    try {
      const [q, r] = await Promise.allSettled([
        testApi.nextQuestion(payload.sessionId),
        testApi.getResult(payload.sessionId),
      ])
      if (q.status === 'fulfilled') {
        progress.setQuestion(q.value)
      } else {
        // 拉不到题 = 会话已完成
        result.markFinished()
      }
      if (r.status === 'fulfilled') {
        result.setResult(r.value)
      }
    } finally {
      loadingState.value = 'idle'
    }
  }

  async function loadNextQuestion() {
    if (!sessionId.value) return
    loadingState.value = 'fetching'
    error.value = null
    try {
      await progress.loadNextQuestion()
    } catch (e) {
      const err = e as ApiError
      // 409 表示已经答完
      if (err.status === 409) {
        result.markFinished()
        await fetchResult()
      } else {
        error.value = err.message || '获取题目失败'
      }
    } finally {
      loadingState.value = 'idle'
    }
  }

  async function submitAnswer(answer: AnswerValue) {
    if (!currentQuestion.value || !sessionId.value) return
    loadingState.value = 'submitting'
    error.value = null
    try {
      const resp = await answers.submit(answer)
      if (resp.completed) {
        result.markFinished()
        await fetchResult()
      } else if (progress.advanceToCachedOrNull()) {
        // 回退修改后重新作答：缓存用尽则向后端取下一题
        await loadNextQuestion()
      }
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : '提交答案失败'
    } finally {
      loadingState.value = 'idle'
    }
  }

  /** 回退到上一题（仅限已显示过、有缓存的题）。 */
  function goBack() {
    if (!canGoBack.value || loading.value) return
    progress.goBack()
  }

  /** 回退状态下前进到下一题（缓存优先，回到进度点则向后端取题）。 */
  async function goNext() {
    if (!canGoNext.value || loading.value) return
    if (progress.advanceToCachedOrNull()) {
      await loadNextQuestion()
    }
  }

  async function fetchResult() {
    if (!sessionId.value) return
    loadingState.value = 'result'
    error.value = null
    try {
      await result.fetchResult()
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : '获取结果失败'
    } finally {
      loadingState.value = 'idle'
    }
  }

  /** 从缓存的 sessionStorage 直接恢复结果（无需后端 API，用于刷新结果页）。 */
  function restoreFromCache(sid: string, cachedResult: ResultResponse) {
    result.restoreFromCache(sid, cachedResult)
  }

  return {
    // 状态
    sessionId,
    total,
    currentIndex,
    currentQuestion,
    answers: answersMap,
    seenQuestions,
    progressIndex,
    canGoBack,
    canGoNext,
    result: resultValue,
    loadingState,
    loading,
    isLoading,
    error,
    finished,
    progress: progressPercent,
    answeredCount,
    // 方法
    startSession,
    loadNextQuestion,
    submitAnswer,
    goBack,
    goNext,
    fetchResult,
    hydrate,
    restoreFromCache,
    reset,
  }
})
