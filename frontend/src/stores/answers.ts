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
 *
 * 本地缓存（#4 回退体验）：每次提交后把 {question_id: answer} 写入
 * localStorage（key = quxu:answers:<sessionId>），供「刷新恢复进度 + 返回上一题
 * 恢复选中态」使用；重新开始测试 / 退出测试时由门面调用 clearPersisted 清除。
 * ============================================================================
 */

const STORAGE_PREFIX = 'quxu:answers:'

function storageKey(sessionId: string): string {
  return `${STORAGE_PREFIX}${sessionId}`
}

function readPersisted(sessionId: string): Record<string, AnswerValue> {
  try {
    const raw = localStorage.getItem(storageKey(sessionId))
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return {}
    const out: Record<string, AnswerValue> = {}
    for (const [k, v] of Object.entries(parsed)) {
      if (v === 'Y' || v === 'N') out[k] = v
    }
    return out
  } catch {
    return {}
  }
}

function writePersisted(sessionId: string, answers: Record<string, AnswerValue>) {
  try {
    localStorage.setItem(storageKey(sessionId), JSON.stringify(answers))
  } catch {
    // ignore（例如隐私模式配额不足）
  }
}

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
    // 本地缓存：刷新后恢复已选答案
    writePersisted(session.sessionId, answers.value)
    return resp
  }

  /** 从 localStorage 恢复该会话的已答答案（刷新恢复进度用）。 */
  function restoreFromStorage(sessionId: string) {
    answers.value = readPersisted(sessionId)
  }

  /** 清除某会话的本地答案缓存（重新开始/退出测试时调用）。 */
  function clearPersisted(sessionId: string) {
    if (!sessionId) return
    try {
      localStorage.removeItem(storageKey(sessionId))
    } catch {
      // ignore
    }
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
    restoreFromStorage,
    clearPersisted,
    reset,
  }
})
