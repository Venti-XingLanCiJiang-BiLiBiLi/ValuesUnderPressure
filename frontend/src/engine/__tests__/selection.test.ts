/**
 * selection.ts 单元测试：桶驱动抽题 + seed 可复现 + 配额分布 + 无重复。
 *
 * 移植 backend/tests/test_selection.py 的断言（使用正式题库分桶索引）。
 *
 * 覆盖需求：
 *   - 抽题依赖分桶索引（BucketBank）懒加载桶，不加载全量题库；
 *   - 某组（m 桶、d 题）抽 n 题：先抽 k=min(n,m) 桶；候选不足 n 题时重复抽桶补充；
 *     桶内随机取题不重复；
 *   - d < n 时按 fallback 补齐；
 *   - must / experimental 特殊组抽题；
 *   - 整卷默认 50 题、相同 seed 可复现、无重复题。
 */

import { describe, expect, it } from 'vitest'
import { BucketBank } from '../bank'
import { Rng } from '../rng'
import {
  DEFAULT_LENGTH,
  EXPERIMENTAL_TARGET,
  MUST_TARGET,
  buildTest,
  drawFromGroup,
} from '../selection'
import type { RawQuestion } from '../types'

/** 测试用虚拟题库：题目列表按 Python 测试的 _raw 结构构造。 */
function raw(qid: string, dim: string, bucket: number): RawQuestion {
  return {
    id: qid,
    content: `question ${qid}`,
    type: 'YN',
    category: 'social',
    difficulty: 'easy',
    tags: [dim],
    weights: [{ dimension: dim, yes: bucket, no: -bucket }],
    metadata: { version: 1, status: 'active' },
  }
}

/** 从原始题目列表构建虚拟 BucketBank（对应 Python 测试的 _make_bank）。 */
function makeBank(raws: RawQuestion[], bucketSize = 2): BucketBank {
  return BucketBank.fromQuestions(raws, bucketSize)
}

// ---------------------------------------------------------------------------
// drawFromGroup：桶驱动抽题
// ---------------------------------------------------------------------------

describe('drawFromGroup 桶驱动抽题', () => {
  it('从正式维度组（10 桶 40 题）抽 5 题：恰好 5 题、无重复、均属该主维度', () => {
    const bank = BucketBank.load()
    const group = bank.group('self_protection')
    const picked = drawFromGroup(group!, 5, new Rng(1), bank, new Set())
    const ids = picked.map((q) => q.id)
    expect(picked).toHaveLength(5)
    expect(new Set(ids).size).toBe(5)
    expect(picked.every((q) => q.weights[0].dimension === 'self_protection')).toBe(true)
  })

  it('排除已选题后，不会抽到 excludeIds 中的题', () => {
    const bank = BucketBank.load()
    const group = bank.group('altruism')
    const exclude = new Set(bank.questionsInGroup('altruism').slice(0, 5).map((q) => q.id))
    const picked = drawFromGroup(group!, 3, new Rng(2), bank, exclude)
    expect(picked.every((q) => !exclude.has(q.id))).toBe(true)
  })

  it('n > m（要抽的题数超过桶数）时：先抽全部 m 桶，再从中随机取 n 题', () => {
    // 6 题 / 每桶 2 题 = 3 桶，d=6，n=4 > m=3
    const raws = [
      raw('T01', 'freedom', 1), raw('T02', 'freedom', 2),
      raw('T03', 'freedom', 3), raw('T04', 'freedom', 4),
      raw('T05', 'freedom', 5), raw('T06', 'freedom', -1),
    ]
    const b = makeBank(raws, 2)
    const group = b.group('freedom')
    expect(group!.files).toHaveLength(3)
    const picked = drawFromGroup(group!, 4, new Rng(7), b, new Set())
    expect(picked).toHaveLength(4)
    expect(new Set(picked.map((q) => q.id)).size).toBe(4)
  })

  it('d < n 时：返回该组全部可用题（上层按 fallback 补齐）', () => {
    const raws = [raw('T01', 'freedom', 1), raw('T02', 'freedom', 2)]
    const b = makeBank(raws, 2) // d=2, m=1
    const group = b.group('freedom')
    const picked = drawFromGroup(group!, 3, new Rng(1), b, new Set())
    expect(picked).toHaveLength(2) // 只有 2 题可抽
  })

  it('相同 seed 可复现', () => {
    const bank = BucketBank.load()
    const group = bank.group('wealth')
    const a1 = drawFromGroup(group!, 5, new Rng(9), bank, new Set())
    const a2 = drawFromGroup(group!, 5, new Rng(9), bank, new Set())
    expect(a1.map((q) => q.id)).toEqual(a2.map((q) => q.id))
  })
})

// ---------------------------------------------------------------------------
// 整卷组卷
// ---------------------------------------------------------------------------

describe('buildTest 整卷组卷', () => {
  it('默认长度 50', () => {
    const bank = BucketBank.load()
    const qs = buildTest(bank, { seed: 1 })
    expect(qs).toHaveLength(DEFAULT_LENGTH)
    expect(DEFAULT_LENGTH).toBe(50)
  })

  it('相同 seed 可复现', () => {
    const bank = BucketBank.load()
    const t1 = buildTest(bank, { seed: 42 })
    const t2 = buildTest(bank, { seed: 42 })
    expect(t1.map((q) => q.id)).toEqual(t2.map((q) => q.id))
    expect(t1).toHaveLength(DEFAULT_LENGTH)
  })

  it('默认 50 题组成: must 5 + experimental 1 + 常规维度 44', () => {
    const bank = BucketBank.load()
    const qs = buildTest(bank, { seed: 3 })
    const mustCount = qs.filter((q) => q.category === 'must').length
    const expCount = qs.filter((q) => q.category === 'experimental').length
    const regular = qs.length - mustCount - expCount
    expect(mustCount).toBe(MUST_TARGET)
    expect(expCount).toBe(EXPERIMENTAL_TARGET)
    expect(regular).toBe(DEFAULT_LENGTH - MUST_TARGET - EXPERIMENTAL_TARGET)
  })

  it('默认 50 题时: 常规部分恰好 4 个维度抽 5 题、6 个维度抽 4 题', () => {
    const bank = BucketBank.load()
    const qs = buildTest(bank, { seed: 5 })
    const primary = new Map<string, number>()
    for (const q of qs) {
      if (q.category === 'must' || q.category === 'experimental') continue
      const d = q.weights[0].dimension
      primary.set(d, (primary.get(d) ?? 0) + 1)
    }
    const counts = [...primary.values()]
    expect(counts.filter((c) => c === 5)).toHaveLength(4)
    expect(counts.filter((c) => c === 4)).toHaveLength(6)
  })

  it('无重复题目', () => {
    const bank = BucketBank.load()
    const qs = buildTest(bank, { seed: 3 })
    const ids = qs.map((q) => q.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('非默认长度按比例缩放常规维度配额，总数等于 length', () => {
    const bank = BucketBank.load()
    for (const length of [20, 60]) {
      const qs = buildTest(bank, { length, seed: 2 })
      expect(qs).toHaveLength(length)
      const mustCount = qs.filter((q) => q.category === 'must').length
      const expCount = qs.filter((q) => q.category === 'experimental').length
      expect(mustCount).toBe(MUST_TARGET)
      expect(expCount).toBe(EXPERIMENTAL_TARGET)
    }
  })

  it('length 超出 [10, 120] 时被钳制', () => {
    const bank = BucketBank.load()
    expect(buildTest(bank, { length: 5, seed: 2 })).toHaveLength(10)
    expect(buildTest(bank, { length: 999, seed: 2 })).toHaveLength(120)
  })

  it('指定 dimensions 时，试卷只包含匹配指定维度的题目', () => {
    const bank = BucketBank.load()
    const qs = buildTest(bank, { length: 30, dimensions: ['privacy'], seed: 4 })
    expect(qs.every((q) => q.dimensions.includes('privacy'))).toBe(true)
    expect(qs).toHaveLength(30)
  })
})
