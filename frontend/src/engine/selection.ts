/**
 * 桶驱动随机组卷算法（移植自 backend/app/selection.py）。
 *
 * 规则（默认 50 题）:
 *   - 组卷按分桶索引中的维度组抽题，不加载全量题库；
 *   - 每组抽题采用「先抽桶、再在桶内随机取题」：
 *       · 某组 m 桶、d 题，抽 n 题（d >= n）时，先抽 k = min(n, m) 桶（不放回随机）；
 *       · 候选不足 n 题时，重复抽桶（从剩余桶继续随机抽取）补充；
 *       · 从候选中随机取 n 题，不重复；
 *       · 组内总题数 d < n 时，按 fallback（从其它组补齐）处理；
 *   - must / experimental 作为特殊组参与抽题；
 *   - 整卷最后校验是否有重复题，若有则按 fallback 重抽该题；
 *   - 放弃按难度（easy / medium / hard）分层抽取。
 *
 * 随机数使用 ./rng.ts 的 Rng（同 seed 可复现）。
 */

import type { BucketBank } from './bank'
import { DIMENSION_IDS } from './bank'
import type { Question } from './types'
import { Rng } from './rng'

export const MIN_LENGTH = 10
export const MAX_LENGTH = 120
export const DEFAULT_LENGTH = 50

// must: 每张试卷固定抽 MUST_TARGET 题（锚定题）
export const MUST_TARGET = 5
// experimental: 每张试卷固定抽 1 题
export const EXPERIMENTAL_TARGET = 1

// 分桶索引中的特殊组名
export const MUST_GROUP = 'must'
export const EXP_GROUP = 'experimental'

export interface BuildTestOptions {
  length?: number
  dimensions?: string[] | null
  seed?: number | null
}

/**
 * 从某组（m 桶、d 题）抽 n 题（桶驱动）。
 * 移植自 backend/app/selection.py `_draw_from_group`。
 *
 * 规则（d >= n 时）：
 *   1. 先抽 k = min(n, m) 桶（不放回随机）；
 *   2. 收集这 k 桶全部题目作为候选；
 *   3. 候选不足 n 题时，重复抽桶（从剩余桶继续随机抽取）补充，直到候选 >= n
 *      或所有桶都被抽过；
 *   4. 从候选中随机取 n 题，不重复（排除 excludeIds 与已取题目）。
 *
 * 返回抽到的题目列表（可能少于 n —— 组内可用题不足时，由上层 fallback 补齐）。
 */
export function drawFromGroup(
  group: { files: { path: string; questions: number }[] },
  n: number,
  rng: Rng,
  bank: BucketBank,
  excludeIds: Set<string>,
): Question[] {
  const files = [...group.files]
  const m = files.length
  if (n <= 0 || files.length === 0) {
    return []
  }

  const exclude = new Set(excludeIds)
  const pool: Question[] = []
  const seen = new Set(exclude)
  const loadedPaths = new Set<string>()

  const absorb = (f: { path: string; questions: number }): void => {
    if (loadedPaths.has(f.path)) {
      return
    }
    loadedPaths.add(f.path)
    for (const q of bank.loadBucket(f.path)) {
      if (!seen.has(q.id)) {
        pool.push(q)
        seen.add(q.id)
      }
    }
  }

  // 1) 先抽 k 桶
  const k = Math.min(n, m)
  for (const f of rng.sample(files, k)) {
    absorb(f)
  }

  // 2) 候选不足 n 题：重复抽桶（从剩余桶随机补充）
  const rest = files.filter((f) => !loadedPaths.has(f.path))
  rng.shuffle(rest)
  for (const f of rest) {
    if (pool.length >= n) {
      break
    }
    absorb(f)
  }

  // 3) 从候选中随机取 n 题，不重复
  rng.shuffle(pool)
  return pool.slice(0, n)
}

/**
 * 去重校验：若出现重复题，该题按 fallback 从未选题目中重抽替换。
 * 移植自 backend/app/selection.py `_dedupe_with_fallback`。
 */
export function dedupeWithFallback(
  bank: BucketBank,
  selected: Question[],
  rng: Rng,
  dimSet: Set<string> | null,
): Question[] {
  const seen = new Set<string>()
  const result: Question[] = []

  let extraPool: Question[] = []
  for (const g of bank.groups()) {
    extraPool.push(...bank.questionsInGroup(g.name))
  }
  if (dimSet !== null) {
    extraPool = extraPool.filter((q) =>
      q.dimensions.some((d) => dimSet.has(d)),
    )
  }
  rng.shuffle(extraPool)
  let ei = 0

  for (const q of selected) {
    if (seen.has(q.id)) {
      while (ei < extraPool.length && seen.has(extraPool[ei]!.id)) {
        ei += 1
      }
      if (ei < extraPool.length) {
        const repl = extraPool[ei]!
        result.push(repl)
        seen.add(repl.id)
        ei += 1
      }
      // 无可用替换时跳过该重复题，保持结果无重复
    } else {
      result.push(q)
      seen.add(q.id)
    }
  }
  return result
}

/**
 * 按分桶索引生成一份随机试卷（桶驱动，无难度分层）。
 * 移植自 backend/app/selection.py `build_test`。
 *
 * - must: 固定抽 MUST_TARGET(5) 题（桶驱动）；
 * - experimental: 固定抽 1 题；
 * - 其余维度组: 均分剩余名额（默认 50 题时，随机挑 4 个维度各抽 5 题、
 *   其余 6 个维度各抽 4 题），每组内按「先抽桶、再抽题」的方式抽取；
 * - 组内题数不足（d < n）时按 fallback 补齐（优先级：维度组 → must → experimental）；
 * - 整卷最后校验重复题，若有则按 fallback 重抽；
 * - 相同 seed 下结果可复现。
 *
 * 如果指定 `dimensions`：只从这些维度组抽题，且题目须包含指定维度；
 * 缺口按相同优先级回补，回补题同样限定维度。
 */
export function buildTest(
  bank: BucketBank,
  options: BuildTestOptions = {},
): Question[] {
  const length = Math.max(MIN_LENGTH, Math.min(MAX_LENGTH, options.length ?? DEFAULT_LENGTH))
  const dimSet = options.dimensions ? new Set(options.dimensions) : null
  const rng = new Rng(options.seed ?? null)

  const groups = bank.groups()
  const dimGroups = groups.filter((g) => g.type === 'dimension')
  const mustGroup = bank.group(MUST_GROUP)
  const expGroup = bank.group(EXP_GROUP)

  const selected: Question[] = []
  const taken = new Set<string>()

  // 辅助：判断题目是否匹配指定维度（未指定时全部通过）
  const matchesDim = (q: Question): boolean => {
    if (dimSet === null) {
      return true
    }
    return q.dimensions.some((d) => dimSet.has(d))
  }

  const take = (qs: Question[]): void => {
    for (const q of qs) {
      if (q !== null && !taken.has(q.id)) {
        selected.push(q)
        taken.add(q.id)
      }
    }
  }

  // 1) must（锚定题）
  if (mustGroup) {
    take(drawFromGroup(mustGroup, MUST_TARGET, rng, bank, taken))
  }

  // 2) experimental
  if (expGroup) {
    take(drawFromGroup(expGroup, EXPERIMENTAL_TARGET, rng, bank, taken))
  }

  // 3) 常规维度组：均分剩余名额，余数随机分配给部分维度
  let remaining = Math.max(0, length - selected.length)
  let poolGroups = dimGroups.filter(
    (g) => dimSet === null || dimSet.has(g.name),
  )
  if (poolGroups.length === 0) {
    poolGroups = [...dimGroups] // 指定维度不存在时回退到全部维度
  }
  if (remaining > 0 && poolGroups.length > 0) {
    const base = Math.floor(remaining / poolGroups.length)
    const extra = remaining % poolGroups.length
    const quotas = new Map<string, number>()
    for (const g of poolGroups) {
      quotas.set(g.name, base)
    }
    for (const g of rng.sample(poolGroups, extra)) {
      quotas.set(g.name, (quotas.get(g.name) ?? 0) + 1)
    }
    for (const g of poolGroups) {
      const n = quotas.get(g.name) ?? 0
      if (n <= 0) {
        continue
      }
      take(drawFromGroup(g, n, rng, bank, taken))
    }
  }

  // 3.5) 维度筛选：指定 dimensions 时只保留匹配题
  if (dimSet) {
    const filtered = selected.filter((q) => matchesDim(q))
    selected.length = 0
    selected.push(...filtered)
    taken.clear()
    for (const q of selected) {
      taken.add(q.id)
    }
  }

  // 4) 回补缺口（优先级：维度组 → must → experimental）
  let shortfall = length - selected.length
  if (shortfall > 0) {
    const fb: Question[] = []
    for (const g of poolGroups) {
      for (const q of bank.questionsInGroup(g.name)) {
        if (!taken.has(q.id) && matchesDim(q)) {
          fb.push(q)
        }
      }
    }
    rng.shuffle(fb)
    take(fb.slice(0, shortfall))
  }

  shortfall = length - selected.length
  if (shortfall > 0 && mustGroup) {
    const fb = bank
      .questionsInGroup(MUST_GROUP)
      .filter((q) => !taken.has(q.id) && matchesDim(q))
    rng.shuffle(fb)
    take(fb.slice(0, shortfall))
  }

  shortfall = length - selected.length
  if (shortfall > 0 && expGroup) {
    const fb = bank
      .questionsInGroup(EXP_GROUP)
      .filter((q) => !taken.has(q.id) && matchesDim(q))
    rng.shuffle(fb)
    take(fb.slice(0, shortfall))
  }

  // 5) 去重校验 + fallback 重抽
  const deduped = dedupeWithFallback(bank, selected, rng, dimSet)
  selected.length = 0
  selected.push(...deduped)

  rng.shuffle(selected)
  return selected
}

/**
 * 返回本次试卷对各维度的覆盖题数，便于调试/单测。
 * 移植自 backend/app/selection.py `coverage_report`。
 */
export function coverageReport(questions: Question[]): Record<string, number> {
  const report: Record<string, number> = {}
  for (const d of DIMENSION_IDS) {
    report[d] = 0
  }
  for (const q of questions) {
    for (const d of q.dimensions) {
      report[d] = (report[d] ?? 0) + 1
    }
  }
  return report
}
