/**
 * 本地存档 composable
 * ============================================================================
 * 每次答完题后，把结果自动保存到 localStorage，供首页"存档"入口查看与回顾。
 *
 * 工作机制：
 * 1. 测试完成（fetchResult 拿到 completed 结果）后调用 saveArchive()
 * 2. 同一 session 重复保存会覆盖（按 session_id 去重），最新在前，最多 MAX_ARCHIVES 条
 * 3. 首页列出存档，点击进入 /archive/:sessionId 查看，可单独删除
 *
 * 用 localStorage 而不是 sessionStorage：
 * - 存档是长期数据，关闭浏览器后仍保留，方便日后回顾
 * - 数据仅存本地，不上传服务器
 * ============================================================================
 */

import { ref } from 'vue'
import type { ResultResponse } from '@/types/api'

const STORAGE_KEY = 'quxu:archives'
const MAX_ARCHIVES = 50

export interface ArchiveEntry {
  sessionId: string
  savedAt: number
  result: ResultResponse
}

function readAll(): ArchiveEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as ArchiveEntry[]) : []
  } catch {
    return []
  }
}

function writeAll(list: ArchiveEntry[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
  } catch {
    // ignore（例如隐私模式配额不足）
  }
}

// 模块级单例：所有消费者共享同一份响应式列表
const archives = ref<ArchiveEntry[]>(readAll())

export function useArchives() {
  /** 保存一条存档（相同 session 覆盖，返回是否新增）。 */
  function saveArchive(result: ResultResponse) {
    const existed = archives.value.some((a) => a.sessionId === result.session_id)
    const rest = archives.value.filter((a) => a.sessionId !== result.session_id)
    const entry: ArchiveEntry = {
      sessionId: result.session_id,
      savedAt: Date.now(),
      result,
    }
    archives.value = [entry, ...rest].slice(0, MAX_ARCHIVES)
    writeAll(archives.value)
    return !existed
  }

  /** 按 sessionId 读取一条存档。 */
  function getArchive(sessionId: string): ArchiveEntry | null {
    return archives.value.find((a) => a.sessionId === sessionId) ?? null
  }

  /** 删除一条存档。 */
  function deleteArchive(sessionId: string) {
    archives.value = archives.value.filter((a) => a.sessionId !== sessionId)
    writeAll(archives.value)
  }

  /** 清空全部存档。 */
  function clearArchives() {
    archives.value = []
    writeAll(archives.value)
  }

  return {
    archives,
    saveArchive,
    getArchive,
    deleteArchive,
    clearArchives,
  }
}
