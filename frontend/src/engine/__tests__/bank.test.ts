/**
 * bank.ts 单元测试：重建桶与索引一致性。
 *
 * 覆盖：
 *   - 正式题库 500 题、id 唯一、每组桶数/题数匹配分桶索引；
 *   - 组内题目主维度正确（dimension 组权重主维度 = 组名）；
 *   - freedom 桶结构（80 题、20 桶、每桶 4 题、每主权重桶拆 2 块）；
 *   - 桶成员与真实桶文件完全一致（抽查若干桶的精确 id）；
 *   - validateRawQuestion / toQuestion 校验逻辑；
 *   - fromQuestions 虚拟分桶（测试回退）。
 */

import { describe, expect, it } from 'vitest'
import {
  BucketBank,
  DIMENSION_IDS,
  VALID_DIFFICULTY,
  bank,
  buildVirtualIndex,
  toQuestion,
  validateRawQuestion,
} from '../bank'
import type { RawQuestion } from '../types'

function raw(qid: string, dim: string, yes: number, no = -yes): RawQuestion {
  return {
    id: qid,
    content: `question ${qid}`,
    type: 'YN',
    category: 'social',
    difficulty: 'easy',
    tags: [dim],
    weights: [{ dimension: dim, yes, no }],
    metadata: { version: 1, status: 'active' },
  }
}

describe('正式题库加载与重建', () => {
  it('共 500 题且全部有效（校验无异常记录）', () => {
    expect(bank.totalQuestions()).toBe(500)
    expect(bank.invalid).toEqual([])
    expect(bank.activeQuestions()).toHaveLength(500)
  })

  it('id 全局唯一（跨组聚合后仍为 500 个不重复 id）', () => {
    const ids = bank.activeQuestions().map((q) => q.id)
    expect(new Set(ids).size).toBe(500)
    // id 按 Q00001..Q00500 升序连续
    const sorted = [...ids].sort()
    expect(sorted[0]).toBe('Q00001')
    expect(sorted[sorted.length - 1]).toBe('Q00500')
  })

  it('每组桶数 / 题数与索引一致', () => {
    let total = 0
    for (const group of bank.groups()) {
      total += group.question_count
      expect(group.files).toHaveLength(group.bucket_count)
      const fileSum = group.files.reduce((s, f) => s + f.questions, 0)
      expect(fileSum).toBe(group.question_count)
      expect(bank.questionsInGroup(group.name)).toHaveLength(group.question_count)
    }
    expect(total).toBe(500)
    expect(bank.totalQuestions()).toBe(total)
  })

  it('组内题目主维度正确（dimension 组）', () => {
    for (const group of bank.groups()) {
      if (group.type !== 'dimension') continue
      const qs = bank.questionsInGroup(group.name)
      expect(qs.length).toBeGreaterThan(0)
      for (const q of qs) {
        expect(q.weights[0].dimension).toBe(group.name)
        expect(q.category).not.toBe('must')
        expect(q.category).not.toBe('experimental')
      }
    }
  })

  it('freedom 桶结构：80 题 / 20 桶 / 每桶 4 题 / 每主权重桶拆 2 块', () => {
    const group = bank.group('freedom')
    expect(group).not.toBeNull()
    expect(group!.question_count).toBe(80)
    expect(group!.bucket_count).toBe(20)
    expect(group!.bucket_size).toBe(4)
    for (const f of group!.files) {
      expect(f.questions).toBe(4)
      expect(bank.loadBucket(f.path)).toHaveLength(4)
    }
    // 每个主权重桶恰好 2 个文件（8 题拆 2 块）
    const buckets = group!.files.map((f) => f.bucket)
    expect(new Set(buckets).size).toBe(10)
    const perBucket = new Map<string, number>()
    for (const b of buckets) perBucket.set(b, (perBucket.get(b) ?? 0) + 1)
    for (const count of perBucket.values()) {
      expect(count).toBe(2)
    }
  })

  it('must / experimental 特殊组结构与分类一致', () => {
    const must = bank.group('must')
    expect(must!.bucket_count).toBe(10)
    expect(must!.question_count).toBe(40)
    expect(bank.questionsInGroup('must').every((q) => q.category === 'must')).toBe(true)

    const exp = bank.group('experimental')
    expect(exp!.bucket_count).toBe(1)
    expect(exp!.question_count).toBe(20)
    expect(bank.questionsInGroup('experimental').every((q) => q.category === 'experimental')).toBe(
      true,
    )
  })
})

describe('桶成员重建与真实桶文件一致（抽查精确 id）', () => {
  it('self_protection SP_Bnk5 = Q00001..Q00004', () => {
    const qs = bank.loadBucket('questions/self_protection/SP_Bnk5.json')
    expect(qs.map((q) => q.id)).toEqual(['Q00001', 'Q00002', 'Q00003', 'Q00004'])
  })

  it('altruism AL_Bnk-1 = Q00061..Q00064（负权重桶）', () => {
    const qs = bank.loadBucket('questions/altruism/AL_Bnk-1.json')
    expect(qs.map((q) => q.id)).toEqual(['Q00061', 'Q00062', 'Q00063', 'Q00064'])
  })

  it('freedom FD_Bnk-1_1 / FD_Bnk-1_2 同权重桶拆 2 块', () => {
    expect(bank.loadBucket('questions/freedom/FD_Bnk-1_1.json').map((q) => q.id)).toEqual([
      'Q00101',
      'Q00102',
      'Q00103',
      'Q00104',
    ])
    expect(bank.loadBucket('questions/freedom/FD_Bnk-1_2.json').map((q) => q.id)).toEqual([
      'Q00421',
      'Q00422',
      'Q00423',
      'Q00424',
    ])
  })

  it('must Must_Bnk01 = Q00441..Q00444；experimental Exp_Bnk01 = Q00481..Q00500', () => {
    expect(bank.loadBucket('questions/must/Must_Bnk01.json').map((q) => q.id)).toEqual([
      'Q00441',
      'Q00442',
      'Q00443',
      'Q00444',
    ])
    const expIds = bank.loadBucket('questions/experimental/Exp_Bnk01.json').map((q) => q.id)
    expect(expIds).toHaveLength(20)
    expect(expIds[0]).toBe('Q00481')
    expect(expIds[expIds.length - 1]).toBe('Q00500')
  })

  it('bucket 加载有缓存（同一 path 返回同一数组引用）', () => {
    const path = 'questions/wealth/WE_Bnk3.json'
    expect(bank.loadBucket(path)).toBe(bank.loadBucket(path))
  })
})

describe('版本与访问器', () => {
  it('version 返回 v1，维度列表来自 dimensions.json', () => {
    expect(bank.version()).toBe('v1')
    expect(DIMENSION_IDS).toHaveLength(10)
    expect(DIMENSION_IDS).toContain('freedom')
    expect(DIMENSION_IDS).toContain('long_term')
  })

  it('get 按 id 取题，未加载的组懒加载命中；不存在返回 null', () => {
    const q = bank.get('Q00001')
    expect(q).not.toBeNull()
    expect(q!.content.length).toBeGreaterThan(0)
    expect(q!.type).toBe('YN')
    expect(bank.get('NOT_EXIST')).toBeNull()
  })
})

describe('validateRawQuestion 校验逻辑', () => {
  it('合法题目无错误', () => {
    expect(validateRawQuestion(raw('T1', 'freedom', 3), new Set())).toEqual([])
  })

  it('id 缺失 / 重复', () => {
    expect(validateRawQuestion({ ...raw('T1', 'freedom', 1), id: '' }, new Set())).toContain(
      '缺少 id',
    )
    expect(validateRawQuestion(raw('T1', 'freedom', 1), new Set(['T1']))).toEqual([
      'id 重复: T1',
    ])
  })

  it('content 空 / type 非 YN / difficulty 非法', () => {
    expect(validateRawQuestion({ ...raw('T1', 'freedom', 1), content: '' }, new Set())).toEqual(
      ['[T1] content 不能为空'],
    )
    expect(validateRawQuestion({ ...raw('T1', 'freedom', 1), type: 'AB' }, new Set())).toEqual([
      '[T1] type 必须为 YN',
    ])
    expect(
      validateRawQuestion({ ...raw('T1', 'freedom', 1), difficulty: 'insane' }, new Set()),
    ).toEqual(['[T1] difficulty 非法: insane'])
    expect(VALID_DIFFICULTY).toContain('easy')
  })

  it('weights 空 / 未知维度 / 维度重复', () => {
    expect(validateRawQuestion({ ...raw('T1', 'freedom', 1), weights: [] }, new Set())).toEqual([
      '[T1] weights 至少包含一个维度',
    ])
    const unknown = raw('T1', 'freedom', 1)
    unknown.weights = [{ dimension: 'nope', yes: 1, no: -1 }]
    expect(validateRawQuestion(unknown, new Set())).toEqual(['[T1] 未知维度: nope'])
    const dup = raw('T1', 'freedom', 1)
    dup.weights = [
      { dimension: 'freedom', yes: 1, no: -1 },
      { dimension: 'freedom', yes: 2, no: -2 },
    ]
    expect(validateRawQuestion(dup, new Set())).toEqual(['[T1] 维度重复: freedom'])
  })

  it('权重超出 -5~5 / yes no 同时为 0', () => {
    const out = raw('T1', 'freedom', 6)
    expect(validateRawQuestion(out, new Set())[0]).toContain('权重 yes 超出 -5~5')
    const zero = raw('T1', 'freedom', 1)
    zero.weights = [{ dimension: 'freedom', yes: 0, no: 0 }]
    expect(validateRawQuestion(zero, new Set())).toEqual(['[T1] yes 和 no 不能同时为 0'])
  })

  it('metadata.version 非正整数 / status 非法', () => {
    const v0 = raw('T1', 'freedom', 1)
    v0.metadata = { version: 0, status: 'active' }
    expect(validateRawQuestion(v0, new Set())).toEqual([
      '[T1] metadata.version 必须为正整数',
    ])
    const bad = raw('T1', 'freedom', 1)
    bad.metadata = { version: 1, status: 'weird' }
    expect(validateRawQuestion(bad, new Set())).toEqual(['[T1] metadata.status 非法: weird'])
  })
})

describe('toQuestion 转换', () => {
  it('合法原始题转为 Question（权重解析、getter 可用）', () => {
    const r = raw('T1', 'freedom', 3)
    const q = toQuestion(r)
    expect(q).not.toBeNull()
    expect(q!.id).toBe('T1')
    expect(q!.weights).toEqual([{ dimension: 'freedom', yes: 3, no: -3 }])
    expect(q!.status).toBe('active')
    expect(q!.dimensions).toEqual(['freedom'])
  })

  it('无 weights / 结构非法返回 null', () => {
    expect(toQuestion({ ...raw('T1', 'freedom', 1), weights: [] })).toBeNull()
  })
})

describe('fromQuestions 虚拟分桶（测试回退）', () => {
  it('按主维度分组 + 按 bucketSize 切桶', () => {
    const raws = [
      raw('T01', 'freedom', 1),
      raw('T02', 'freedom', 2),
      raw('T03', 'freedom', 3),
      raw('T04', 'freedom', 4),
      raw('T05', 'freedom', 5),
      raw('T06', 'security', 1),
    ]
    const b = BucketBank.fromQuestions(raws, 2)
    expect(b.totalQuestions()).toBe(6)
    const freedom = b.group('freedom')
    expect(freedom).not.toBeNull()
    expect(freedom!.bucket_count).toBe(3)
    expect(freedom!.files).toHaveLength(3)
    expect(b.questionsInGroup('freedom')).toHaveLength(5)
    expect(b.questionsInGroup('security')).toHaveLength(1)
  })

  it('buildVirtualIndex 与 fromQuestions 行为一致', () => {
    const raws = [raw('T1', 'freedom', 1), raw('T2', 'freedom', 2)]
    const index = buildVirtualIndex(raws, 2)
    expect(index.total_questions).toBe(2)
    expect(index.groups).toHaveLength(1)
    expect(index.groups[0]!.name).toBe('freedom')
    expect(index.groups[0]!.bucket_count).toBe(1)
    expect(index.groups[0]!.files[0]!.path).toBe('__mem__/freedom/0')
  })
})
