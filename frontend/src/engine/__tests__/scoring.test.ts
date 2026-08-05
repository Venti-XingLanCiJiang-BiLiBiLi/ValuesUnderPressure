/**
 * scoring.ts 单元测试：归一化 (0-100)、min/max possible、一致性。
 *
 * 移植 backend/tests/test_scoring.py 的断言。
 *
 * 覆盖修复点：
 *   1. min/max possible 只基于已作答题目计算（与 raw 同基准），
 *      保证 score 0-100 正确表示价值倾向强度；
 *   2. 一致性按"作答方向符号"统计：对每维比较各题方向代数和
 *      （|Σ sign|）与绝对值代数和（n）的差距，输出 0~1，样本不足返回 null；
 *   3. 维度级置信度 confidence（题量 / 一致性 / 权重覆盖三信号）。
 */

import { describe, expect, it } from 'vitest'
import {
  CONSISTENCY_LOW_THRESHOLD,
  HIGH_SCORE_THRESHOLD,
  MIN_QUESTION_THRESHOLD,
  consistency,
  dimensionConfidence,
  scoreSession,
} from '../scoring'
import { Question, type Weight } from '../types'

// 4 道仅覆盖 altruism 的题，权重两两互为反向，方便手算预期值。
// 单题可能贡献区间 [-3, +3]；4 题全答时 min=-12 / max=+12。
function altruismQuestion(id: string, yes: number, no: number): Question {
  return new Question(
    id,
    'q',
    'YN',
    'social',
    'easy',
    [],
    [{ dimension: 'altruism', yes, no }],
    { version: 1, status: 'active' },
  )
}

const RAW_ALTRUISM: Question[] = [
  altruismQuestion('A1', -3, 3),
  altruismQuestion('A2', -3, 3),
  altruismQuestion('A3', 3, -3),
  altruismQuestion('A4', 3, -3),
]

// ---------------------------------------------------------------------------
// 归一化
// ---------------------------------------------------------------------------

describe('归一化 (0-100)', () => {
  it('raw=0 -> 50 分（价值倾向强度居中的中性位置）', () => {
    const answers = { A1: 'Y', A2: 'N', A3: 'Y', A4: 'N' }
    const r = scoreSession(RAW_ALTRUISM, answers).dimensions['altruism']
    expect(r.min_possible).toBe(-12)
    expect(r.max_possible).toBe(12)
    expect(r.raw_score).toBe(0)
    expect(r.score).toBe(50.0)
  })

  it('全部指向 direction[1] -> 100 分', () => {
    const answers = { A1: 'N', A2: 'N', A3: 'Y', A4: 'Y' }
    const r = scoreSession(RAW_ALTRUISM, answers).dimensions['altruism']
    expect(r.raw_score).toBe(12)
    expect(r.score).toBe(100.0)
  })

  it('全部指向 direction[0] -> 0 分', () => {
    const answers = { A1: 'Y', A2: 'Y', A3: 'N', A4: 'N' }
    const r = scoreSession(RAW_ALTRUISM, answers).dimensions['altruism']
    expect(r.raw_score).toBe(-12)
    expect(r.score).toBe(0.0)
  })

  it('回归测试：min/max 只基于已作答题目（只答 A1/A2 时）', () => {
    // 只作答 A1/A2（贡献 -3 各一）时：
    //   - 修复前：min/max 按全部 4 题算（-12/12），raw=-6 -> 25 分（错误）；
    //   - 修复后：min/max 只按已作答 2 题算（-6/6），raw=-6 -> 0 分。
    const answers = { A1: 'Y', A2: 'Y' }
    const r = scoreSession(RAW_ALTRUISM, answers).dimensions['altruism']
    expect(r.question_count).toBe(2)
    expect(r.min_possible).toBe(-6)
    expect(r.max_possible).toBe(6)
    expect(r.raw_score).toBe(-6)
    expect(r.score).toBe(0.0)
  })

  it('score 始终在 0~100 内', () => {
    const answers = { A1: 'N', A2: 'Y', A3: 'N', A4: 'Y' }
    const r = scoreSession(RAW_ALTRUISM, answers).dimensions['altruism']
    expect(r.score).toBeGreaterThanOrEqual(0.0)
    expect(r.score).toBeLessThanOrEqual(100.0)
  })
})

// ---------------------------------------------------------------------------
// 一致性
// ---------------------------------------------------------------------------

describe('一致性（按作答方向符号统计）', () => {
  it('方向一致 / 抵消 / 混合', () => {
    expect(consistency([5, 5])).toBe(1.0) // 完全一致
    expect(consistency([5, -5])).toBe(0.0) // 完全抵消
    expect(consistency([1, 1, -1, -1])).toBe(0.0)
    // 各题方向代数和 vs 绝对值代数和：|Σ sign| / n
    expect(consistency([5, 3, -1])).toBe(0.33) // 2 同 1 反
    expect(consistency([5, -1, -1])).toBe(0.33) // 1 同 2 反
    // 权重大小不放大敏感度：大权重反向也只算一个方向
    expect(consistency([5, -5, -1])).toBe(0.33)
    expect(consistency([5, 5, -1])).toBe(0.33)
    // 8/9 同向不应被判为情境依赖（修复"过于敏感"）
    expect(consistency([5, 5, 5, 5, 5, 5, 5, 5, -5])).toBe(0.78)
  })

  it('有效样本不足时返回 null', () => {
    expect(consistency([])).toBeNull()
    expect(consistency([5])).toBeNull()
    expect(consistency([0, 5])).toBeNull()
    expect(consistency([0, 0])).toBeNull()
  })

  it('c==0 无方向贡献不计入一致性样本', () => {
    // [0,5,5] -> 有效样本 [5,5]，方向一致 -> 1.0
    expect(consistency([0, 5, 5])).toBe(1.0)
    // [0,5,-5] -> 有效样本 [5,-5]，方向抵消 -> 0.0
    expect(consistency([0, 5, -5])).toBe(0.0)
    // [0,0] -> 无有效样本 -> null
    expect(consistency([0, 0])).toBeNull()
  })

  it('输出范围 0~1', () => {
    for (const contribs of [[5, 4], [5, -4], [3, 1, -2], [1, 2, 3, -6]]) {
      const value = consistency(contribs)
      expect(value).not.toBeNull()
      expect(value!).toBeGreaterThanOrEqual(0.0)
      expect(value!).toBeLessThanOrEqual(1.0)
    }
  })

  it('低一致性维度应进入 uncertain_dimensions', () => {
    // 矛盾作答：contribs: -3,+3,-3,+3
    const answers = { A1: 'Y', A2: 'N', A3: 'N', A4: 'Y' }
    const result = scoreSession(RAW_ALTRUISM, answers)
    expect(result.dimensions['altruism'].consistency).toBe(0.0)
    expect(result.uncertain_dimensions).toContain('altruism')
  })

  it('CONSISTENCY_LOW_THRESHOLD 为 0.5', () => {
    expect(CONSISTENCY_LOW_THRESHOLD).toBe(0.5)
  })
})

// ---------------------------------------------------------------------------
// 维度级置信度 confidence
// ---------------------------------------------------------------------------

const FULL_CONSISTENT = { A1: 'N', A2: 'N', A3: 'Y', A4: 'Y' } // 全答且方向一致
const FULL_CONTRADICT = { A1: 'Y', A2: 'N', A3: 'N', A4: 'Y' } // 全答但矛盾
const PARTIAL_2Q = { A1: 'Y', A2: 'Y' } // 只答一半

describe('维度级置信度 confidence', () => {
  it('维度结果包含 confidence 且范围在 0~1；全答一致 -> 高置信度', () => {
    const r = scoreSession(RAW_ALTRUISM, FULL_CONSISTENT).dimensions['altruism']
    expect(r.confidence).toBeGreaterThanOrEqual(0.0)
    expect(r.confidence).toBeLessThanOrEqual(1.0)
    expect(r.confidence).toBeGreaterThan(0.5)
  })

  it('高度矛盾的回答会拉低 confidence', () => {
    const consistent = scoreSession(RAW_ALTRUISM, FULL_CONSISTENT).dimensions['altruism']
    const contradict = scoreSession(RAW_ALTRUISM, FULL_CONTRADICT).dimensions['altruism']
    expect(contradict.confidence).toBeLessThan(consistent.confidence)
  })

  it('同等作答质量下，题量/权重覆盖不足会拉低 confidence', () => {
    const full = scoreSession(RAW_ALTRUISM, FULL_CONSISTENT).dimensions['altruism']
    const partial = scoreSession(RAW_ALTRUISM, PARTIAL_2Q).dimensions['altruism']
    expect(partial.question_count).toBe(2)
    expect(full.question_count).toBe(4)
    expect(partial.confidence).toBeLessThan(full.confidence)
  })

  it('相同一致性/覆盖下，题量越少 confidence 越低（<5 时自动衰减）', () => {
    const low = dimensionConfidence(2, 0.5, 0.5)
    const high = dimensionConfidence(8, 0.5, 0.5)
    expect(low).toBeLessThan(high)
    expect(low).toBeLessThan(0.5)
  })

  it('无作答题目时 confidence 为 0', () => {
    expect(dimensionConfidence(0, null, 0.0)).toBe(0.0)
  })

  it('confidence 始终落在 0~1', () => {
    const cases: [number, number | null, number][] = [
      [0, null, 0.0],
      [50, 1.0, 1.0],
      [3, 0.0, 0.2],
    ]
    for (const [count, cons, cov] of cases) {
      const value = dimensionConfidence(count, cons, cov)
      expect(value).toBeGreaterThanOrEqual(0.0)
      expect(value).toBeLessThanOrEqual(1.0)
    }
  })

  it('MIN_QUESTION_THRESHOLD 为 5', () => {
    expect(MIN_QUESTION_THRESHOLD).toBe(5)
  })
})

// ---------------------------------------------------------------------------
// 矛盾分析 conflicts
// ---------------------------------------------------------------------------

describe('矛盾分析 conflicts', () => {
  function mk(id: string, weights: Weight[]): Question {
    return new Question(id, 'q', 'YN', 'social', 'easy', [], weights, {
      version: 1,
      status: 'active',
    })
  }

  it('freedom 与 security 同时高分时输出矛盾项（HIGH_SCORE_THRESHOLD=60）', () => {
    expect(HIGH_SCORE_THRESHOLD).toBe(60)
    const questions = [
      mk('F1', [{ dimension: 'freedom', yes: -5, no: 5 }]),
      mk('F2', [{ dimension: 'freedom', yes: -5, no: 5 }]),
      mk('F3', [{ dimension: 'freedom', yes: -5, no: 5 }]),
      mk('F4', [{ dimension: 'freedom', yes: -5, no: 5 }]),
      mk('S1', [{ dimension: 'security', yes: -5, no: 5 }]),
      mk('S2', [{ dimension: 'security', yes: -5, no: 5 }]),
      mk('S3', [{ dimension: 'security', yes: -5, no: 5 }]),
      mk('S4', [{ dimension: 'security', yes: -5, no: 5 }]),
    ]
    const answers: Record<string, string> = {}
    for (const q of questions) answers[q.id] = 'N' // 全部指向 direction[1] -> 100 分
    const result = scoreSession(questions, answers)
    expect(result.dimensions['freedom'].score).toBe(100)
    expect(result.dimensions['security'].score).toBe(100)
    const conflict = result.conflicts.find((c) => c.dimensions[0] === 'freedom')
    expect(conflict).toBeDefined()
    expect(conflict!.dimensions).toEqual(['freedom', 'security'])
    expect(conflict!.names).toHaveLength(2)
    expect(conflict!.description.length).toBeGreaterThan(0)
  })

  it('单边高分不产生矛盾项；未覆盖维度不输出', () => {
    const questions = [
      mk('F1', [{ dimension: 'freedom', yes: -5, no: 5 }]),
      mk('F2', [{ dimension: 'freedom', yes: -5, no: 5 }]),
    ]
    const answers = { F1: 'N', F2: 'N' }
    const result = scoreSession(questions, answers)
    expect(result.conflicts).toEqual([])
    expect(result.dimensions['security']).toBeUndefined()
    expect(result.dimensions['freedom']).toBeDefined()
  })
})
