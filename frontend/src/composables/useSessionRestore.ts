/**
 * 答题进度恢复 composable
 * ============================================================================
 * 刷新页面 / 关闭浏览器再打开时，自动恢复上次的 session_id 和结果。
 *
 * 工作机制：
 * 1. 创建会话成功后，把 session_id + 已答题目数写入 sessionStorage
 * 2. 应用启动时（App.vue onMounted），读 sessionStorage 尝试恢复
 * 3. 如果后端还能查到该会话（GET /question 成功），自动跳到 /test
 * 4. 如果会话已失效（404/409），清空缓存回到开屏
 * 5. 结果页刷新时，从 sessionStorage 恢复缓存的测试结果（无需后端）
 *
 * 用 sessionStorage 而不是 localStorage：
 * - 关闭浏览器标签页即清除（更符合"测试是临时任务"的语义）
 * - 不跨标签页共享（避免多窗口互相覆盖）
 * ============================================================================
 */

import { ref } from 'vue'
import { sessionManager } from '@/engine'
import type { ResultResponse } from '@/types/api'

const STORAGE_KEY = 'quxu:session'
const RESULT_KEY = 'quxu:result'

interface PersistedSession {
  sessionId: string
  total: number
  completed: boolean
  savedAt: number
}

interface CachedResult {
  sessionId: string
  result: ResultResponse
  savedAt: number
}

function read(): PersistedSession | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw) as PersistedSession
    // 24 小时过期 — 防止用户几天前的中断会话被错误恢复
    if (Date.now() - data.savedAt > 24 * 60 * 60 * 1000) return null
    return data
  } catch {
    return null
  }
}

export function useSessionRestore() {
  const restoring = ref(false)
  const restoreError = ref<string | null>(null)

  function persist(sessionId: string, total: number, completed = false) {
    const data: PersistedSession = { sessionId, total, completed, savedAt: Date.now() }
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch {
      // ignore
    }
  }

  /** 缓存测试结果到 sessionStorage，以便刷新结果页时恢复。 */
  function persistResult(sessionId: string, result: ResultResponse) {
    const data: CachedResult = { sessionId, result, savedAt: Date.now() }
    try {
      sessionStorage.setItem(RESULT_KEY, JSON.stringify(data))
    } catch {
      // ignore
    }
  }

  /** 读取缓存的测试结果（无需后端 API）。 */
  function loadCachedResult(): CachedResult | null {
    try {
      const raw = sessionStorage.getItem(RESULT_KEY)
      if (!raw) return null
      const data = JSON.parse(raw) as CachedResult
      if (Date.now() - data.savedAt > 24 * 60 * 60 * 1000) return null
      return data
    } catch {
      return null
    }
  }

  /** 清扫残留的答案/进度本地缓存：按命名空间前缀全量清除，不依赖会话数据是否存在。 */
  function sweepLocalCaches() {
    try {
      // localStorage 持久、可能跨会话残留（旧标签页/崩溃/会话数据已过期），全量清扫
      const answerKeys: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i)
        if (k && k.startsWith('quxu:answers:')) answerKeys.push(k)
      }
      answerKeys.forEach((k) => localStorage.removeItem(k))

      // 进度缓存随标签页关闭自动清除，这里兜底清当前标签页的残留
      const progressKeys: string[] = []
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i)
        if (k && k.startsWith('quxu:progress:')) progressKeys.push(k)
      }
      progressKeys.forEach((k) => sessionStorage.removeItem(k))
    } catch {
      // ignore
    }
  }

  function clear() {
    try {
      // 即使会话数据已丢失（sessionStorage 被清 / 24h 过期 / 跨标签页），
      // 也能清掉 localStorage 里残留的答案缓存，避免脏数据累积。
      sweepLocalCaches()
      sessionStorage.removeItem(STORAGE_KEY)
      sessionStorage.removeItem(RESULT_KEY)
    } catch {
      // ignore
    }
  }

  /**
   * 尝试恢复上次的会话。返回是否成功。
   * 调用方根据结果决定是否跳转到 /test。
   */
  async function tryRestore(): Promise<PersistedSession | null> {
    const data = read()
    if (!data) return null
    restoring.value = true
    restoreError.value = null
    try {
      // 本地探活：会话持久化在 localStorage（引擎 sessionManager），
      // 无需网络。会话已删除或已完成时清缓存（与后端 404/409 语义一致）。
      const info = sessionManager.getSessionInfo(data.sessionId)
      if (!info || info.completed) {
        clear()
        return null
      }
      // 顺便更新 total（防止题库版本变化导致题数不一致）
      return { ...data, total: info.total }
    } finally {
      restoring.value = false
    }
  }

  return {
    restoring,
    restoreError,
    persist,
    persistResult,
    loadCachedResult,
    clear,
    tryRestore,
  }
}
