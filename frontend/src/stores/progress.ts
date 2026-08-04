import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { testApi } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import type { QuestionResponse } from '@/types/api'

/**
 * 答题进度与导航 store（#18）
 * ============================================================================
 * 职责：只管理"当前题目、浏览位置、已显示题目缓存"。
 * - currentQuestion：当前展示的题（缓存或后端拉取）
 * - currentIndex：当前浏览位置（可回退查看已答题目）
 * - seenQuestions：按 index 缓存的已显示题目（供「上一题」回退）
 * - progressIndex：顺序答题进度（后端指针，回退查看不回退）
 * 提供：拉取下一题、回退/前进、缓存推进。
 * ============================================================================
 */

export const useProgressStore = defineStore('progress', () => {
  const currentIndex = ref(0)
  const currentQuestion = ref<QuestionResponse | null>(null)
  const seenQuestions = ref<Record<number, QuestionResponse>>({})
  const progressIndex = ref(0)
  const questionStartTime = ref(0)

  /** 是否可以回退到上一题（上一题已显示过且缓存存在）。 */
  const canGoBack = computed(
    () => currentIndex.value > 0 && !!seenQuestions.value[currentIndex.value - 1],
  )

  /** 回退状态（正在查看已答题目）时是否可前进。 */
  const canGoNext = computed(() => currentIndex.value < progressIndex.value)

  /** 把后端返回的题目设为当前题，并更新浏览位置与缓存。 */
  function setQuestion(q: QuestionResponse) {
    currentQuestion.value = q
    currentIndex.value = q.index
    seenQuestions.value[q.index] = q
    progressIndex.value = q.index
    questionStartTime.value = Date.now()
  }

  /** 向后端取下一题。无会话时返回 null，取不到时抛错（由调用方处理 409 等）。 */
  async function loadNextQuestion(): Promise<QuestionResponse | null> {
    const session = useSessionStore()
    if (!session.sessionId) return null
    const q = await testApi.nextQuestion(session.sessionId)
    setQuestion(q)
    return q
  }

  /** 回退到上一题（仅限已显示过、有缓存的题）。 */
  function goBack() {
    if (!canGoBack.value) return
    currentIndex.value -= 1
    currentQuestion.value = seenQuestions.value[currentIndex.value]
    questionStartTime.value = Date.now()
  }

  /**
   * 回退状态下前进到下一题（缓存优先）。
   * @returns 若已回到进度点（缓存用尽），返回 true 表示调用方应继续 loadNextQuestion()。
   */
  function advanceToCachedOrNull(): boolean {
    const next = currentIndex.value + 1
    if (next < progressIndex.value) {
      currentIndex.value = next
      currentQuestion.value = seenQuestions.value[next]
      questionStartTime.value = Date.now()
      return false
    }
    return true
  }

  function reset() {
    currentIndex.value = 0
    currentQuestion.value = null
    seenQuestions.value = {}
    progressIndex.value = 0
    questionStartTime.value = 0
  }

  return {
    currentIndex,
    currentQuestion,
    seenQuestions,
    progressIndex,
    questionStartTime,
    canGoBack,
    canGoNext,
    setQuestion,
    loadNextQuestion,
    goBack,
    advanceToCachedOrNull,
    reset,
  }
})
