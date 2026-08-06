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
 * - 摘要含 `session_id`：保存按 session 幂等去重，同一会话云端只保留一份；
 *   列表加载时同步清理历史遗留的无 session_id 重复条目（内容指纹合并，云端一并删除）。
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
  /** 会话 id：用于云端按 session 幂等去重；旧存档可能缺失。 */
  session_id?: string
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
    session_id: result.session_id,
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
   * 幂等：按 session_id 去重，同一会话重复保存会先删除旧历史份（含其分块），云端只留一份。
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

      // 读当前云端快照，基于它计算需要移除的 key（同 session 旧份 + 容量超限最旧份）。
      const all = await toy.getCloudStorage()

      // 1) 幂等：同一 session 的旧历史份（含其完整结果分块）先删除，
      //    保证一次测试在云端只保留一份存档；latest 之后会被本次写入覆盖。
      const toRemove: string[] = []
      for (const [key, raw] of Object.entries(all)) {
        if (!isHistoryKey(key)) continue
        const e = parseEntry(raw)
        if (e?.session_id && e.session_id === entry.session_id) {
          const ts = historyTimestamp(key)
          toRemove.push(key, ...(ts === null ? [] : resultChunkKeys(all, ts)))
        }
      }

      // 2) 容量管理：本次将写入 h<ts>、latest 与（若保存完整结果）chunks.length 个分块；
      //    若写入后超过 128 上限，删除最旧的若干历史份（含其分块）腾出配额。
      const historyKeys = Object.keys(all)
        .filter((k) => isHistoryKey(k) && !toRemove.includes(k))
        .sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)))
      const hasLatest = KEY_LATEST in all
      const addedKeys = (hasLatest ? 1 : 2) + (resultSaved ? chunks.length : 0)
      const afterSessionDedupe = Object.keys(all).length - toRemove.length
      let overflow = afterSessionDedupe + addedKeys - MAX_KEYS
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
   * 列出云端存档摘要（去重后按时间倒序），并顺手清理云端重复数据：
   * - 新条目按 session_id 幂等去重（同一会话只保留最新一份）；
   * - 旧条目（无 session_id，如历史上同一次结果被多次保存产生的重复）按内容指纹合并，
   *   仅保留最新一份，其余连同其完整结果分块一并从云端删除（即"老数据云端也去重"）。
   * 非 Toy 环境返回空数组。
   */
  async function listCloudArchives(): Promise<CloudArchiveEntry[]> {
    const toy = await ensureSupported()
    if (!toy) return []
    try {
      const all = await toy.getCloudStorage()

      // 候选 = latest 指针 + 所有历史摘要（结果分块 key 不参与）。
      type Cand = { key: string; ts: number | null; entry: CloudArchiveEntry }
      const candidates: Cand[] = []
      for (const [key, raw] of Object.entries(all)) {
        if (key !== KEY_LATEST && !isHistoryKey(key)) continue
        const entry = parseEntry(raw)
        if (!entry) continue
        candidates.push({
          key,
          ts: key === KEY_LATEST ? null : historyTimestamp(key),
          entry,
        })
      }

      // 分组键：优先 session_id；旧数据无 session_id 时退回内容指纹
      // （q / 置信度(容差到万分位) / 矛盾数 / 维度分数）。同一结果多次保存 → 指纹相同。
      const groupKeyOf = (e: CloudArchiveEntry) =>
        e.session_id
          ? `s:${e.session_id}`
          : `c:${e.q}|${Math.round(e.c * 10000)}|${e.cf}|${JSON.stringify(e.dims)}`

      const groups = new Map<string, Cand[]>()
      for (const c of candidates) {
        const gk = groupKeyOf(c.entry)
        const arr = groups.get(gk) ?? []
        arr.push(c)
        groups.set(gk, arr)
      }

      // 同组只保留最新一份；其余删除 h<ts> 与其完整结果分块（latest 指针永不删除）。
      const byTs = new Map<number, CloudArchiveEntry>()
      const toRemove: string[] = []
      for (const arr of groups.values()) {
        arr.sort((a, b) => (b.ts ?? -1) - (a.ts ?? -1))
        const [keep, ...rest] = arr
        byTs.set(keep.ts ?? keep.entry.t, keep.entry)
        for (const dup of rest) {
          if (dup.key === KEY_LATEST) continue
          toRemove.push(dup.key)
          if (dup.ts !== null) toRemove.push(...resultChunkKeys(all, dup.ts))
        }
      }
      if (toRemove.length > 0) {
        await toy.removeCloudStorage(toRemove)
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
