import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { testApi } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import { useProgressStore } from '@/stores/progress'
import type {
  AnswerHistoryEntry,
  AnswerValue,
  SubmitAnswerResponse,
} from '@/types/api'

/**
 * 答案管理 store（#18）
 * ============================================================================
 * 职责：只管理"已提交的答案"。
 * - answers：question_id → AnswerValue（Y/N）
 * - history：后端返回的修改历史（answer_history）
 * 提供 submit()：提交当前题的答案并记录；不负责导航/结果（由门面编排）。
 * ============================================================================
 */

export const useAnswerStore = defineStore('answers', () => {
  const answers = ref<Record<string, AnswerValue>>({})
  const history = ref<AnswerHistoryEntry[]>([])

  const answeredCount = computed(() => Object.keys(answers.value).length)

  /** 提交当前题答案；返回后端响应（导航/完成判断由调用方编排）。 */
  async function submit(answer: AnswerValue): Promise<SubmitAnswerResponse> {
    const session = useSessionStore()
    const progress = useProgressStore()
    const q = progress.currentQuestion
    if (!q || !session.sessionId) {
      throw new Error('无当前题目或会话，无法提交答案')
    }
    const duration = Math.max(
      0,
      Math.round((Date.now() - progress.questionStartTime) / 1000),
    )
    const resp = await testApi.submitAnswer(session.sessionId, {
      question_id: q.question_id,
      answer,
      duration,
    })
    answers.value[q.question_id] = answer
    if (resp.answer_history) history.value = resp.answer_history
    return resp
  }

  function reset() {
    answers.value = {}
    history.value = []
  }

  return {
    answers,
    history,
    answeredCount,
    submit,
    reset,
  }
})
