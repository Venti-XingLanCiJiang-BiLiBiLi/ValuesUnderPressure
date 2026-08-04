import { defineStore } from 'pinia'
import { ref } from 'vue'
import { testApi } from '@/api/client'

/**
 * 会话元数据 store（#18）
 * ============================================================================
 * 职责：只管理"当前测试会话"的身份信息与生命周期状态。
 * - sessionId：后端会话 ID
 * - total：本次测试总题数
 * - status：idle（未开始）| active（进行中）| completed（已完成）
 * 创建会话、从恢复数据注入会话、标记完成、重置。
 * 不关心题目、答案、结果等具体数据。
 * ============================================================================
 */

export type SessionStatus = 'idle' | 'active' | 'completed'

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref<string | null>(null)
  const total = ref(0)
  const status = ref<SessionStatus>('idle')

  /** 写入会话元数据（可由 create / restore / hydrate 调用）。 */
  function setSession(id: string, count: number, s: SessionStatus = 'active') {
    sessionId.value = id
    total.value = count
    status.value = s
  }

  /** 创建新会话（调用后端 /test/session）。 */
  async function create(length = 50) {
    const session = await testApi.createSession({ length })
    setSession(session.session_id, session.question_count, 'active')
  }

  /** 从恢复数据注入会话（刷新页面后恢复进度用）。 */
  function restore(sid: string, count: number) {
    setSession(sid, count, 'active')
  }

  /** 标记会话已完成。 */
  function markCompleted() {
    status.value = 'completed'
  }

  function reset() {
    sessionId.value = null
    total.value = 0
    status.value = 'idle'
  }

  return {
    sessionId,
    total,
    status,
    setSession,
    create,
    restore,
    markCompleted,
    reset,
  }
})
