/**
 * Toy 云存档 composable（结果云备份，按 B 站账号隔离）
 * ============================================================================
 * 通过 Toy SDK 云存储（getCloudStorage / setCloudStorage / removeCloudStorage）
 * 把测试结果摘要备份到云端。按「登录用户 + Toy」双维度隔离 —— 每人独立，
 * 跨设备跟随登录态持久化。
 *
 * 容量与格式（受 SDK 限制约束）：
 * - 单个 Toy 最多 128 个 key；key 只能含字母/数字/下划线/短横线且不能以 __ 开头；
 * - value ≤ 1024 字节 —— 所以只存摘要（分数/置信度/时间），不存完整结果文案；
 * - key 设计：`latest` = 最新一份；`h<时间戳>` = 历史份；
 *   写满 128 个时自动删除最旧的历史份。
 * - 需要用户已登录；未登录 / 非 Toy 环境 / 失败时静默降级，不打断主流程。
 * ============================================================================
 */
import { ref } from 'vue'
import type { ResultResponse } from '@/types/api'
import { getToy } from '@/composables/useToy'

/** 云存档单条摘要（value ≤1024B 约束内）。 */
export interface CloudArchiveEntry {
  /** 结构版本。 */
  v: 1
  /** 保存时间戳（毫秒）。 */
  t: number
  /** 已作答数。 */
  q: number
  /** 整体置信度 0~1。 */
  c: number
  /** 矛盾组合数。 */
  cf: number
  /** 各维度分数：dimension → score。 */
  dims: Record<string, number>
}

export interface CloudSaveResult {
  ok: boolean
  /** 失败原因（供 UI 提示）。 */
  reason?: string
}

const KEY_LATEST = 'latest'
const KEY_HISTORY_PREFIX = 'h'
const MAX_KEYS = 128
const ENTRY_VERSION = 1 as const

function toEntry(result: ResultResponse, ts = Date.now()): CloudArchiveEntry {
  const dims: Record<string, number> = {}
  for (const [dim, d] of Object.entries(result.dimensions)) {
    dims[dim] = d.score
  }
  return {
    v: ENTRY_VERSION,
    t: ts,
    q: result.answered_count,
    c: result.confidence ?? 0,
    cf: result.conflicts.length,
    dims,
  }
}

function parseEntry(raw: string): CloudArchiveEntry | null {
  try {
    const e = JSON.parse(raw) as CloudArchiveEntry
    if (e && e.v === ENTRY_VERSION && typeof e.t === 'number' && e.dims) {
      return e
    }
    return null
  } catch {
    return null
  }
}

function historyKey(ts: number): string {
  return `${KEY_HISTORY_PREFIX}${ts}`
}

function isHistoryKey(key: string): boolean {
  return key.startsWith(KEY_HISTORY_PREFIX)
}

/** 序列化后的大小是否符合 SDK value ≤1024B 约束。 */
export function entrySizeOk(entry: CloudArchiveEntry): boolean {
  return JSON.stringify(entry).length <= 1024
}

/** 从 key 提取历史时间戳；非历史 key 返回 null。 */
export function historyTimestamp(key: string): number | null {
  if (!isHistoryKey(key)) return null
  const ts = Number(key.slice(KEY_HISTORY_PREFIX.length))
  return Number.isFinite(ts) && ts > 0 ? ts : null
}

// ---------------------------------------------------------------------------
// composable
// ---------------------------------------------------------------------------

/** 是否可用（Toy 环境 + 云存储能力 + 已登录由 SDK 判定）。 */
const supported = ref(false)

/** 检查并缓存云存储能力；每次实际读写前都会自检，避免依赖外部调用 refresh。 */
async function ensureSupported(): Promise<ToySDK.Toy | null> {
  const toy = getToy()
  if (!toy || typeof toy.isSupport !== 'function') {
    supported.value = false
    return null
  }
  try {
    supported.value = await toy.isSupport('getCloudStorage')
  } catch {
    supported.value = false
  }
  return supported.value ? toy : null
}

export function useToyCloudArchive() {
  /**
   * 保存一份结果摘要到云端（latest + h<ts> 双写）。
   * 超出 128 key 上限时先删除最旧历史份；失败返回 {ok:false}，不抛错。
   */
  async function saveToCloud(result: ResultResponse): Promise<CloudSaveResult> {
    const toy = await ensureSupported()
    if (!toy) {
      return { ok: false, reason: 'unsupported' }
    }
    try {
      const entry = toEntry(result)
      if (!entrySizeOk(entry)) {
        return { ok: false, reason: 'too_large' }
      }

      // 容量管理：本次将写入 h<ts> 与 latest 两个 key，
      // 若写入后超过 128 上限，删除最旧的若干历史份腾出配额。
      const all = await toy.getCloudStorage()
      const historyKeys = Object.keys(all)
        .filter(isHistoryKey)
        .sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)))
      const hasLatest = KEY_LATEST in all
      const overflow =
        Object.keys(all).length + (hasLatest ? 1 : 2) - MAX_KEYS
      if (overflow > 0 && historyKeys.length > 0) {
        await toy.removeCloudStorage(historyKeys.slice(0, overflow))
      }

      const payload = JSON.stringify(entry)
      // 先写历史份、再写 latest，latest 始终指向最近一次
      await toy.setCloudStorage({ [historyKey(entry.t)]: payload })
      await toy.setCloudStorage({ [KEY_LATEST]: payload })
      return { ok: true }
    } catch {
      return { ok: false, reason: 'failed' }
    }
  }

  /**
   * 列出云端存档（含 latest，去重后按时间倒序）。
   * 非 Toy 环境返回空数组。
   */
  async function listCloudArchives(): Promise<CloudArchiveEntry[]> {
    const toy = await ensureSupported()
    if (!toy) return []
    try {
      const all = await toy.getCloudStorage()
      const byTs = new Map<number, CloudArchiveEntry>()
      for (const [key, raw] of Object.entries(all)) {
        const ts = key === KEY_LATEST ? null : historyTimestamp(key)
        const entry = parseEntry(raw)
        if (!entry) continue
        if (ts === null && key === KEY_LATEST) {
          byTs.set(entry.t, entry)
        } else if (ts !== null) {
          byTs.set(entry.t, entry)
        }
      }
      return [...byTs.values()].sort((a, b) => b.t - a.t)
    } catch {
      return []
    }
  }

  /** 删除指定时间戳的云端存档（同时清理指向它的 latest 冗余）。 */
  async function deleteCloudArchive(ts: number): Promise<boolean> {
    const toy = await ensureSupported()
    if (!toy) return false
    try {
      const keys = [historyKey(ts)]
      const all = await toy.getCloudStorage()
      const latest = parseEntry(all[KEY_LATEST] ?? '')
      if (latest && latest.t === ts) keys.push(KEY_LATEST)
      await toy.removeCloudStorage(keys)
      return true
    } catch {
      return false
    }
  }

  return {
    supported,
    refreshSupported: ensureSupported,
    saveToCloud,
    listCloudArchives,
    deleteCloudArchive,
  }
}
