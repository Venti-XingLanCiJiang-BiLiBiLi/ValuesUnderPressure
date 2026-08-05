import { defineStore } from 'pinia'
import { ref } from 'vue'
import { testApi } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import { useSessionRestore } from '@/composables/useSessionRestore'
import { useArchives } from '@/composables/useArchives'
import { useToyCloudArchive } from '@/composables/useToyCloudArchive'
import type { ResultResponse } from '@/types/api'

/**
 * 结果与缓存 store（#18）
 * ============================================================================
 * 职责：只管理"测试结果"。
 * - result：ResultResponse（完成后才有）
 * - finished：是否已答完
 * 提供：fetchResult（拉取 + 持久化 + 自动存档）、restoreFromCache（刷新恢复）、
 * setResult / markFinished（供 hydrate 注入）。
 * ============================================================================
 */

export const useResultStore = defineStore('result', () => {
  const result = ref<ResultResponse | null>(null)
  const finished = ref(false)

  /** 从后端拉取结果；完成后缓存到 sessionStorage 并自动存档到 localStorage。 */
  async function fetchResult(): Promise<ResultResponse | null> {
    const session = useSessionStore()
    if (!session.sessionId) return null
    const res = await testApi.getResult(session.sessionId)
    setResult(res)
    // 缓存结果到 sessionStorage，刷新结果页时无需后端即可恢复
    const { persistResult, persist } = useSessionRestore()
    persistResult(session.sessionId, res)
    persist(session.sessionId, session.total, true)
    // 答完自动存档到 localStorage，首页可查看
    if (res.completed) {
      const { saveArchive } = useArchives()
      saveArchive(res)
      // Toy 环境：结果摘要自动备份到云端（按 B 站账号隔离）。
      // fire-and-forget：失败（未登录 / 非 Toy 环境）不影响主流程。
      const { saveToCloud } = useToyCloudArchive()
      void saveToCloud(res).catch(() => undefined)
    }
    return res
  }

  /** 注入结果（hydrate 等场景使用；completed 时标记完成）。 */
  function setResult(res: ResultResponse) {
    result.value = res
    if (res.completed) {
      const session = useSessionStore()
      session.markCompleted()
      finished.value = true
    }
  }

  /** 标记为已完成（拉取下一题返回 409 等场景）。 */
  function markFinished() {
    finished.value = true
  }

  /** 从缓存的 sessionStorage 直接恢复结果（无需后端 API，用于刷新结果页）。 */
  function restoreFromCache(sid: string, cachedResult: ResultResponse) {
    const session = useSessionStore()
    session.setSession(sid, cachedResult.total, 'completed')
    result.value = cachedResult
    finished.value = true
  }

  function reset() {
    result.value = null
    finished.value = false
  }

  return {
    result,
    finished,
    fetchResult,
    setResult,
    markFinished,
    restoreFromCache,
    reset,
  }
})
