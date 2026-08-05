/**
 * 评分算法实现（移植自 backend/app/scoring.py）。
 *
 * 来源:
 *   docs/ScoringAlgorithm.md  -> 累加 + 归一化(0-100) + 一致性分析
 *   docs/ResultInterpretation.md -> 倾向方向 / 典型行为描述 / 矛盾分析 / 不确定性
 *
 * 维度元数据从题库版本目录的 dimensions.json 导入（与题目同版本打包）；
 * CONFLICT_PAIRS 照抄 backend/app/dimensions.py。
 */

import rawDimensionsJson from '../../../question-bank/v1/dimensions.json'
import type { ConflictItem, DimensionScore } from '../types/api'
import type { Question, RawDimensionMeta, RawDimensionsJson } from './types'

export const CONSISTENCY_LOW_THRESHOLD = 0.5
// 倾向分类阈值与前端 bar 颜色阈值（frontend/src/config/theme.ts SCORE_THRESHOLDS）对齐：
// >= 60 高分倾向 / <= 40 低分倾向 / 40~60 中间地带
export const HIGH_SCORE_THRESHOLD = 60
export const LOW_SCORE_THRESHOLD = 40
// 维度级置信度：低于该题量时 confidence 会按数量因子衰减（样本量不足 -> 低可信）
export const MIN_QUESTION_THRESHOLD = 5

/** 维度元数据（dimensions.json 含 abbr 展示字段，引擎保留原样）。 */
export const DIMENSIONS: Record<string, RawDimensionMeta> =
  rawDimensionsJson as unknown as RawDimensionsJson

export const DIMENSION_IDS: string[] = Object.keys(DIMENSIONS)

/** 结果解读中用于「矛盾分析」的典型高分冲突组合（照抄 dimensions.py）。 */
export const CONFLICT_PAIRS: [string, string][] = [
  ['freedom', 'security'],
  ['altruism', 'self_protection'],
  ['rule_orientation', 'pragmatism'],
  ['collectivism', 'freedom'],
  ['wealth', 'altruism'],
  ['long_term', 'pragmatism'],
  ['collectivism', 'self_protection'],
]

/** 单个维度的评分结果（对应后端 scoring.DimensionResult dataclass）。 */
export interface DimensionResult {
  dimension: string
  name: string
  raw_score: number
  min_possible: number
  max_possible: number
  score: number // 0-100 归一化分数
  consistency: number | null // 0-1，null 表示样本不足
  tendency: string // 描述方向的文字
  description: string
  question_count: number
  confidence: number // 0-1，维度级可信度（综合题量 / 一致性 / 权重覆盖）
}

/** 整卷评分结果（对应后端 scoring.TestResult dataclass）。 */
export interface TestResult {
  dimensions: Record<string, DimensionResult>
  confidence: number
  conflicts: ConflictItem[]
  uncertain_dimensions: string[]
}

function contribution(weightYes: number, weightNo: number, answer: string): number {
  return answer === 'Y' ? weightYes : weightNo
}

/** 四舍五入到 2 位小数（对应 Python round(x, 2) 的常见场景）。 */
function round2(value: number): number {
  return Math.round(value * 100) / 100
}

/** 四舍五入到 1 位小数（对应 Python round(x, 1) 的常见场景）。 */
function round1(value: number): number {
  return Math.round(value * 10) / 10
}

/**
 * 根据已作答的题目计算各维度得分、一致性与矛盾分析。
 * 移植自 backend/app/scoring.py `score_session`。
 *
 * answers: {question_id: "Y" | "N"}，只统计已回答的题目。
 */
export function scoreSession(
  questions: Question[],
  answers: Record<string, string>,
): TestResult {
  const rawScores: Record<string, number> = {}
  const minPossible: Record<string, number> = {}
  const maxPossible: Record<string, number> = {}
  const signedContribs: Record<string, number[]> = {}
  const counts: Record<string, number> = {}

  // 每个维度在本次试卷中的总权重范围（无论是否作答），
  // 用于计算“权重覆盖程度”：已作答题目权重区间 / 该维度全部题目权重区间。
  const totalMinPossible: Record<string, number> = {}
  const totalMaxPossible: Record<string, number> = {}
  for (const q of questions) {
    for (const w of q.weights) {
      const dim = w.dimension
      totalMinPossible[dim] = (totalMinPossible[dim] ?? 0) + Math.min(w.yes, w.no)
      totalMaxPossible[dim] = (totalMaxPossible[dim] ?? 0) + Math.max(w.yes, w.no)
    }
  }

  for (const q of questions) {
    const answer = answers[q.id]
    if (answer !== 'Y' && answer !== 'N') {
      // 未作答的题目不参与任何统计：
      // raw / min / max / 一致性必须基于同一批已作答题目，否则归一化会被
      // 未作答题目的潜在区间"稀释"，分数不再能正确表示价值倾向强度。
      continue
    }
    for (const w of q.weights) {
      const dim = w.dimension
      const contrib = contribution(w.yes, w.no, answer)

      rawScores[dim] = rawScores[dim] ?? 0
      minPossible[dim] = minPossible[dim] ?? 0
      maxPossible[dim] = maxPossible[dim] ?? 0
      signedContribs[dim] = signedContribs[dim] ?? []
      counts[dim] = counts[dim] ?? 0

      rawScores[dim] += contrib
      minPossible[dim] += Math.min(w.yes, w.no)
      maxPossible[dim] += Math.max(w.yes, w.no)
      signedContribs[dim].push(contrib)
      counts[dim] += 1
    }
  }

  const dimResults: Record<string, DimensionResult> = {}
  const consistencies: number[] = []
  const uncertain: string[] = []

  for (const [dim, meta] of Object.entries(DIMENSIONS)) {
    if (!(dim in rawScores) || (counts[dim] ?? 0) === 0) {
      continue // 本次试卷未覆盖该维度，不输出
    }

    const lo = minPossible[dim]!
    const hi = maxPossible[dim]!
    const raw = rawScores[dim]!
    let normalized: number
    if (hi > lo) {
      normalized = ((raw - lo) / (hi - lo)) * 100
    } else {
      normalized = 50.0
    }
    normalized = round1(Math.max(0.0, Math.min(100.0, normalized)))

    const consistencyValue = consistency(signedContribs[dim]!)
    if (consistencyValue !== null) {
      consistencies.push(consistencyValue)
      if (consistencyValue < CONSISTENCY_LOW_THRESHOLD) {
        uncertain.push(dim)
      }
    }

    const [tendency, description] = describe(dim, meta, normalized, consistencyValue)

    // 权重覆盖程度：已作答题目权重区间 / 该维度全部题目权重区间（0~1）。
    const totalSpan =
      (totalMaxPossible[dim] ?? hi) - (totalMinPossible[dim] ?? lo)
    const answeredSpan = hi - lo
    const weightCoverage = totalSpan > 0 ? answeredSpan / totalSpan : 1.0
    const confidenceValue = dimensionConfidence(
      counts[dim]!,
      consistencyValue,
      weightCoverage,
    )

    dimResults[dim] = {
      dimension: dim,
      name: meta.name,
      raw_score: raw,
      min_possible: lo,
      max_possible: hi,
      score: normalized,
      consistency: consistencyValue,
      tendency,
      description,
      question_count: counts[dim]!,
      confidence: confidenceValue,
    }
  }

  const overallConfidence =
    consistencies.length > 0
      ? round2(consistencies.reduce((s, c) => s + c, 0) / consistencies.length)
      : 0.0
  const conflicts = conflictAnalysis(dimResults)

  return {
    dimensions: dimResults,
    confidence: overallConfidence,
    conflicts,
    uncertain_dimensions: uncertain,
  }
}

/**
 * 计算单个维度的可信度 (0-1)。
 * 移植自 backend/app/scoring.py `_dimension_confidence`。
 *
 * 综合三个信号：
 *   1. 权重覆盖程度 weightCoverage（0~1）：已作答题目权重区间占比；
 *   2. 作答一致性 consistency（0~1）：方向越稳定可信度越高，
 *      样本不足（null）或高度矛盾都会拉低置信度；
 *   3. 题目数量 quantity（0~1）：低于 MIN_QUESTION_THRESHOLD 时按比例衰减，
 *      实现“该维度题目数量过少 -> confidence 自动降低”。
 *
 * 权重：0.5 * 覆盖 + 0.3 * 一致性 + 0.2 * 题量。
 */
export function dimensionConfidence(
  questionCount: number,
  consistencyValue: number | null,
  weightCoverage: number,
): number {
  if (questionCount <= 0) {
    return 0.0
  }
  const quantity = Math.min(1.0, questionCount / MIN_QUESTION_THRESHOLD)
  const consistencyFactor = consistencyValue ?? 0.0
  const confidence =
    0.5 * weightCoverage + 0.3 * consistencyFactor + 0.2 * quantity
  return round2(Math.max(0.0, Math.min(1.0, confidence)))
}

/**
 * 同一维度内多题作答方向的一致程度 (0-1)。
 * 移植自 backend/app/scoring.py `_consistency`。
 *
 * 做法: 记录每题对该维度的作答方向（正贡献取 +1，负贡献取 -1），
 * 对每个维度比较各题方向的"代数和 |Σ sign|"与"绝对值代数和 Σ|sign|=n"
 * 的差距：consistency = |Σ sign| / n。
 *
 * - 取值 0~1：1 表示所有作答方向完全一致（稳定倾向），
 *   0 表示同向与反向相互抵消（情境依赖/矛盾）；
 * - 只按方向（符号）统计，不受单题权重大小影响，
 *   避免个别大权重题反向时被过度放大而误判"情境依赖"（过于敏感）；
 * - 有效样本 < 2（无信号）时无法判断，返回 null。
 */
export function consistency(contribs: number[]): number | null {
  // c == 0 表示该题对当前维度无方向性贡献（如 yes=0, no=5 权重设计），
  // 不计入一致性样本。这避免了"中性贡献"被错误地归入正/负方向。
  const signs = contribs.filter((c) => c !== 0).map((c) => (c > 0 ? 1 : -1))
  if (signs.length < 2) {
    return null
  }
  const aligned = Math.abs(signs.reduce((s, x) => s + x, 0)) // 各题方向代数和
  const total = signs.length // 各题方向绝对值代数和（每项 |sign| = 1）
  return round2(aligned / total)
}

/**
 * 根据分数与一致性生成倾向方向与典型行为描述。
 * 移植自 backend/app/scoring.py `_describe`。
 */
export function describe(
  dim: string,
  meta: RawDimensionMeta,
  score: number,
  consistencyValue: number | null,
): [string, string] {
  if (consistencyValue !== null && consistencyValue < CONSISTENCY_LOW_THRESHOLD) {
    return [
      '情境依赖',
      '该价值维度存在较强情境依赖，不同场景下的选择并不稳定，暂不适合归为单一倾向。',
    ]
  }

  if (score >= HIGH_SCORE_THRESHOLD) {
    return [meta.direction[1], meta.high]
  }
  if (score <= LOW_SCORE_THRESHOLD) {
    return [meta.direction[0], meta.low]
  }
  return [
    '中间地带',
    `你在「${meta.direction[0]} vs ${meta.direction[1]}」之间没有非常明确的倾向，更可能依据具体情境权衡。`,
  ]
}

/**
 * 检测典型的高分冲突组合 (docs/ResultInterpretation.md 举例)。
 * 移植自 backend/app/scoring.py `_conflict_analysis`。
 */
export function conflictAnalysis(
  dimResults: Record<string, DimensionResult>,
): ConflictItem[] {
  const conflicts: ConflictItem[] = []
  for (const [a, b] of CONFLICT_PAIRS) {
    const ra = dimResults[a]
    const rb = dimResults[b]
    if (!ra || !rb) {
      continue
    }
    if (ra.score >= HIGH_SCORE_THRESHOLD && rb.score >= HIGH_SCORE_THRESHOLD) {
      conflicts.push({
        dimensions: [a, b],
        names: [ra.name, rb.name],
        description:
          `你同时展现出较高的「${ra.name}」与「${rb.name}」倾向，` +
          '说明你可能在两者间存在复杂的价值平衡，而非简单地偏向一方。',
      })
    }
  }
  return conflicts
}

/** 把维度结果映射为 API 的 DimensionScore（对应 sessions.py 的 dimension_payload）。 */
export function toApiDimension(result: DimensionResult): DimensionScore {
  return {
    dimension: result.dimension,
    name: result.name,
    score: result.score,
    tendency: result.tendency,
    description: result.description,
    consistency: result.consistency,
    question_count: result.question_count,
    confidence: result.confidence,
  }
}
