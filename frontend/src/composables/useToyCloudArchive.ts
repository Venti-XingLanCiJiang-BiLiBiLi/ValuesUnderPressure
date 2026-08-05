/**
 * Toy 云存档 composable（结果云备份，按 B 站账号隔离）
 * ============================================================================
 * 通过 Toy SDK 云存储（getCloudStorage / setCloudStorage / removeCloudStorage）
 * 把测试结果备份到云端。按「登录用户 + Toy」双维度隔离 —— 每人独立，
 * 跨设备跟随登录态持久化。
 *
 * 容量与格式（受 SDK 限制约束）：
 * - 单个 Toy 最多 128 个 key；key 只能含字母/数字/下划线/短横线且不能以 __ 开头；
 * - value ≤ 1024 字节 —— 摘要单 key 存放；完整结果按字节分块存储；
 * - key 设计：`latest` = 最新一份；`h<时间戳>` = 历史摘要；`r<时间戳>_<n>` = 完整结果分块；
 *   写满 128 个 key 时自动删除最旧历史份（含其分块）。
 * - 完整结果过大（超过分块数上限）时自动降级：仅备份摘要（`resultSaved=false`），
 *   latest / 历史摘要仍正常写入。
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
  /** 完整结果分块是否已写入；false = 结果过大降级，仅备份摘要（无法回顾完整结果）。 */
  resultSaved?: boolean
}

const KEY_LATEST = 'latest'
const KEY_HISTORY_PREFIX = 'h'
const KEY_RESULT_PREFIX = 'r'
const MAX_KEYS = 128
const ENTRY_VERSION = 1 as const
/** 完整结果单块上限（字节），给 SDK 1024B 上限留余量。 */
const MAX_CHUNK_BYTES = 900
/** 完整结果分块数上限（≈21KB）；超出时降级为仅备份摘要。 */
const MAX_RESULT_CHUNKS = 24

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

function isResultKey(key: string): boolean {
  return /^r\d+_\d+$/.test(key)
}

/**
 * 按字节把字符串切成 ≤ MAX_CHUNK_BYTES 的分块（不拆散代理对）。
 * value 上限按字节计，中文 JSON 一个字符可能占 3 字节。
 */
function encodeChunks(payload: string): string[] {
  const encoder = new TextEncoder()
  const chunks: string[] = []
  let start = 0
  while (start < payload.length) {
    let end = Math.min(start + 512, payload.length)
    const code = payload.charCodeAt(end - 1)
    if (code >= 0xd800 && code <= 0xdbff) end -= 1
    while (encoder.encode(payload.slice(start, end)).length > MAX_CHUNK_BYTES) {
      end -= 8
    }
    chunks.push(payload.slice(start, end))
    start = end
  }
  return chunks
}

/** 某时间戳存档的结果分块 key（按块号升序）。 */
function resultChunkKeys(all: Record<string, string>, ts: number): string[] {
  const prefix = `${KEY_RESULT_PREFIX}${ts}_`
  return Object.keys(all)
    .filter((k) => k.startsWith(prefix) && isResultKey(k))
    .sort((a, b) => Number(a.slice(prefix.length)) - Number(b.slice(prefix.length)))
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
   * 保存一份结果到云端（latest + h<ts> 摘要双写 + r<ts>_<n> 完整结果分块）。
   * 完整结果过大（超过分块数上限）时自动降级为仅备份摘要（resultSaved=false）。
   * 超出 128 key 上限时先删除最旧历史份（含其分块）；失败返回 {ok:false}，不抛错。
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
      const payload = JSON.stringify(entry)
      const resultPayload = JSON.stringify(result)
      const chunks = encodeChunks(resultPayload)
      // 完整结果过大（超过分块数上限）时降级：仅备份摘要、不写分块。
      // 摘要（维度概要）仍可正常备份与查看，只是无法回顾完整结果。
      const resultSaved = chunks.length <= MAX_RESULT_CHUNKS

      // 容量管理：本次将写入 h<ts>、latest 与（若保存完整结果）chunks.length 个分块；
      // 若写入后超过 128 上限，删除最旧的若干历史份（含其分块）腾出配额。
      const all = await toy.getCloudStorage()
      const historyKeys = Object.keys(all)
        .filter(isHistoryKey)
        .sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)))
      const hasLatest = KEY_LATEST in all
      const addedKeys = (hasLatest ? 1 : 2) + (resultSaved ? chunks.length : 0)
      let overflow = Object.keys(all).length + addedKeys - MAX_KEYS
      const toRemove: string[] = []
      for (const hk of historyKeys) {
        if (overflow <= 0) break
        const ts = historyTimestamp(hk)
        const chunkKeys = ts === null ? [] : resultChunkKeys(all, ts)
        toRemove.push(hk, ...chunkKeys)
        overflow -= 1 + chunkKeys.length
      }
      if (toRemove.length > 0) {
        await toy.removeCloudStorage(toRemove)
      }

      const resultItems: Record<string, string> = {}
      if (resultSaved) {
        chunks.forEach((chunk, i) => {
          resultItems[`${KEY_RESULT_PREFIX}${entry.t}_${i}`] = chunk
        })
      }
      // 写入顺序：先历史摘要 → 再完整结果分块 → 最后 latest。
      // 这样 latest 只在「摘要 + 完整分块均就绪」后指向最新一份；
      // 中途失败时 latest 仍指向旧的完整结果，避免出现「有摘要无分块」的最新项。
      await toy.setCloudStorage({ [historyKey(entry.t)]: payload })
      if (resultSaved) {
        await toy.setCloudStorage(resultItems)
      }
      await toy.setCloudStorage({ [KEY_LATEST]: payload })
      return { ok: true, resultSaved }
    } catch {
      return { ok: false, reason: 'failed' }
    }
  }

  /**
   * 列出云端存档摘要（含 latest，去重后按时间倒序）。
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

  /**
   * 读取某时间戳存档的完整结果（跨 r<ts>_<n> 分块重组）。
   * 缺少分块 / 解析失败 / 非 Toy 环境返回 null。
   */
  async function getCloudResult(ts: number): Promise<ResultResponse | null> {
    const toy = await ensureSupported()
    if (!toy) return null
    try {
      const all = await toy.getCloudStorage()
      const keys = resultChunkKeys(all, ts)
      if (keys.length === 0) return null
      const payload = keys.map((k) => all[k]).join('')
      const result = JSON.parse(payload) as ResultResponse
      if (!result || typeof result !== 'object' || !result.dimensions) return null
      return result
    } catch {
      return null
    }
  }

  /** 删除指定时间戳的云端存档（含完整结果分块与指向它的 latest 冗余）。 */
  async function deleteCloudArchive(ts: number): Promise<boolean> {
    const toy = await ensureSupported()
    if (!toy) return false
    try {
      const keys = [historyKey(ts)]
      const all = await toy.getCloudStorage()
      keys.push(...resultChunkKeys(all, ts))
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
    getCloudResult,
    deleteCloudArchive,
  }
}
