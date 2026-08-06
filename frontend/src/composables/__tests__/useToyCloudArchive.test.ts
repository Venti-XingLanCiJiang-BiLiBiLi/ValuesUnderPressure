/**
 * useToyCloudArchive 单元测试
 * ============================================================================
 * 通过注入假 window.toy（内存存储）验证：
 *   - saveToCloud：latest + h<ts> 双写、摘要符合 value ≤1024B 约束、完整结果分块写入；
 *   - saveToCloud 幂等：同 session 重复保存只留一份（旧 h<ts> 与分块被删除）；
 *   - 容量管理：占满 128 key 时先删最旧历史份（含其分块）再写；
 *   - listCloudArchives：按时间倒序、latest 与 h 同时间戳去重；
 *   - listCloudArchives 清理旧重复数据：内容相同的多条历史仅保留最新，云端删除其余（含分块）；
 *   - getCloudResult：跨 r<ts>_<n> 分块重组完整结果，缺块返回 null；
 *   - deleteCloudArchive：删除 h、结果分块并清理指向它的 latest；
 *   - 非 Toy 环境（无 window.toy）：静默降级不抛错。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  entrySizeOk,
  historyTimestamp,
  useToyCloudArchive,
  type CloudArchiveEntry,
} from '../useToyCloudArchive'
import type { ResultResponse } from '../../types/api'

interface FakeToy {
  store: Record<string, string>
  toy: ToySDK.Toy
}

/** 构造内存版假 Toy SDK（isSupport 全部通过）。 */
function makeFakeToy(initial: Record<string, string> = {}): FakeToy {
  const store: Record<string, string> = { ...initial }
  return {
    store,
    toy: {
      async isSupport() {
        return true
      },
      async getCloudStorage() {
        return { ...store }
      },
      async setCloudStorage(items: Record<string, string>) {
        Object.assign(store, items)
      },
      async removeCloudStorage(keys: string[]) {
        for (const k of keys) delete store[k]
      },
    } as unknown as ToySDK.Toy,
  }
}

function makeResult(overrides: Partial<ResultResponse> = {}): ResultResponse {
  const dims: ResultResponse['dimensions'] = {}
  for (const id of [
    'altruism',
    'collectivism',
    'freedom',
    'long_term',
    'pragmatism',
    'privacy',
    'rule_orientation',
    'security',
    'self_protection',
    'wealth',
  ]) {
    dims[id] = {
      dimension: id,
      name: id,
      score: 42.5,
      tendency: '中间地带',
      description: 'd',
      consistency: 0.8,
      question_count: 4,
      confidence: 0.7,
    }
  }
  return {
    session_id: 's1',
    completed: true,
    answered_count: 50,
    total: 50,
    dimensions: dims,
    confidence: 0.9,
    conflicts: [],
    uncertain_dimensions: [],
    ...overrides,
  }
}

/** 把假 toy 挂到全局（getToy 通过 window.toy 访问）。 */
function mountToy(fake: FakeToy) {
  ;(globalThis as unknown as { window: { toy: ToySDK.Toy } }).window = {
    toy: fake.toy,
  }
}

function unmountToy() {
  delete (globalThis as { window?: unknown }).window
}

beforeEach(() => {
  unmountToy()
})

afterEach(() => {
  unmountToy()
})

describe('工具函数', () => {
  it('entrySizeOk：摘要序列化 ≤1024B（SDK value 上限）', () => {
    const entry: CloudArchiveEntry = {
      v: 1,
      t: 1700000000000,
      q: 50,
      c: 0.95,
      cf: 2,
      dims: Object.fromEntries(
        Array.from({ length: 10 }, (_, i) => [`dimension_${i}_long_name`, 73.2 + i]),
      ),
    }
    expect(entrySizeOk(entry)).toBe(true)
    expect(JSON.stringify(entry).length).toBeLessThanOrEqual(1024)
  })

  it('historyTimestamp：解析历史 key，非历史 key 返回 null', () => {
    expect(historyTimestamp('h1700000000000')).toBe(1700000000000)
    expect(historyTimestamp('latest')).toBeNull()
    expect(historyTimestamp('habc')).toBeNull()
  })
})

describe('saveToCloud', () => {
  it('非 Toy 环境返回 unsupported，不抛错', async () => {
    const { saveToCloud } = useToyCloudArchive()
    const res = await saveToCloud(makeResult())
    expect(res).toEqual({ ok: false, reason: 'unsupported' })
  })

  it('写入 latest 与 h<ts> 两份摘要，完整结果分块可重组', async () => {
    const fake = makeFakeToy()
    mountToy(fake)
    const { saveToCloud, getCloudResult } = useToyCloudArchive()
    const source = makeResult({ confidence: 0.88, answered_count: 70, total: 70 })
    const res = await saveToCloud(source)
    expect(res.ok).toBe(true)
    expect(res.resultSaved).toBe(true)

    const keys = Object.keys(fake.store)
    expect(keys).toContain('latest')
    const historyKeys = keys.filter((k) => k.startsWith('h'))
    expect(historyKeys).toHaveLength(1)

    const entry = JSON.parse(fake.store[historyKeys[0]!]!) as CloudArchiveEntry
    expect(entry.v).toBe(1)
    expect(entry.q).toBe(70)
    expect(entry.c).toBe(0.88)
    expect(Object.keys(entry.dims)).toHaveLength(10)
    // latest 与 h 内容一致
    expect(fake.store.latest).toBe(fake.store[historyKeys[0]!])

    // 完整结果分块写入，且单块 ≤900B
    const resultKeys = keys.filter((k) => /^r\d+_\d+$/.test(k))
    expect(resultKeys.length).toBeGreaterThan(0)
    for (const k of resultKeys) {
      expect(new TextEncoder().encode(fake.store[k]!).length).toBeLessThanOrEqual(900)
    }
    // 重组结果与保存时一致
    const restored = await getCloudResult(entry.t)
    expect(restored).toEqual(source)
  })

  it('同 session 重复保存幂等：旧 h<ts> 与分块被删除，云端只留一份', async () => {
    vi.useFakeTimers()
    try {
      const fake = makeFakeToy()
      mountToy(fake)
      const { saveToCloud } = useToyCloudArchive()
      const source = makeResult({ confidence: 0.88, answered_count: 70, total: 70 })

      // 第一次保存：t=1000
      vi.setSystemTime(1000)
      const first = await saveToCloud(source)
      expect(first.ok).toBe(true)
      expect(Object.keys(fake.store).filter((k) => k.startsWith('h'))).toEqual(['h1000'])

      // 再次保存同一结果（模拟 fetchResult 被多次触发）：t=2000
      vi.setSystemTime(2000)
      const second = await saveToCloud(source)
      expect(second.ok).toBe(true)
      // 同 session 只留一份历史，旧份 h1000 与其完整结果分块已被删除
      expect(Object.keys(fake.store).filter((k) => k.startsWith('h'))).toEqual(['h2000'])
      expect(fake.store.h1000).toBeUndefined()
      expect(Object.keys(fake.store).some((k) => k.startsWith('r1000_'))).toBe(false)
      // 新份完整结果分块已写入
      expect(Object.keys(fake.store).some((k) => k.startsWith('r2000_'))).toBe(true)
    } finally {
      vi.useRealTimers()
    }
  })

  it('完整结果过大时降级：仅备份摘要、不写分块，latest 仍正常写入', async () => {
    const fake = makeFakeToy()
    mountToy(fake)
    const { saveToCloud, getCloudResult } = useToyCloudArchive()
    // 撑大完整结果 JSON 体积（10 个维度 × 超长描述 → 远超分块数上限）
    const dims = makeResult().dimensions
    const source = makeResult({
      dimensions: Object.fromEntries(
        Object.entries(dims).map(([id, d]) => [
          id,
          { ...d, description: '长'.repeat(20000) },
        ]),
      ),
    })
    const res = await saveToCloud(source)
    expect(res.ok).toBe(true)
    expect(res.resultSaved).toBe(false)

    const keys = Object.keys(fake.store)
    // 摘要（latest + h<ts>）正常写入
    expect(keys).toContain('latest')
    expect(keys.some((k) => k.startsWith('h'))).toBe(true)
    // 无完整结果分块，也无法回顾完整结果
    expect(keys.some((k) => /^r\d+_\d+$/.test(k))).toBe(false)
    const entry = JSON.parse(fake.store.latest!) as CloudArchiveEntry
    expect(await getCloudResult(entry.t)).toBeNull()
  })

  it('容量管理：占满 128 key 时先删最旧历史份再写入', async () => {
    const initial: Record<string, string> = {}
    for (let i = 0; i < 127; i++) {
      initial[`h${1000 + i}`] = JSON.stringify({ v: 1, t: 1000 + i, q: 1, c: 0, cf: 0, dims: {} })
    }
    const fake = makeFakeToy(initial)
    mountToy(fake)
    const { saveToCloud } = useToyCloudArchive()
    const res = await saveToCloud(makeResult())
    expect(res.ok).toBe(true)

    const keys = Object.keys(fake.store)
    expect(keys.length).toBeLessThanOrEqual(128)
    // 最旧的历史份 h1000 被清理，latest 存在
    expect(fake.store.h1000).toBeUndefined()
    expect(fake.store.latest).toBeDefined()
    // 新写入的历史份存在
    const newest = Object.keys(fake.store).filter((k) => k.startsWith('h'))
    expect(newest.some((k) => k !== 'h1001' || fake.store[k] !== initial.h1001)).toBe(true)
  })
})

describe('listCloudArchives', () => {
  it('按时间倒序，latest 与历史同时间戳时去重', async () => {
    const entry1 = JSON.stringify({ v: 1, t: 2000, q: 50, c: 0.9, cf: 0, dims: { a: 10 } })
    const entry2 = JSON.stringify({ v: 1, t: 1000, q: 50, c: 0.8, cf: 0, dims: { b: 20 } })
    const fake = makeFakeToy({ h2000: entry1, h1000: entry2, latest: entry1 })
    mountToy(fake)
    const { listCloudArchives } = useToyCloudArchive()
    const list = await listCloudArchives()
    expect(list.map((e) => e.t)).toEqual([2000, 1000])
    expect(list[0]!.dims).toEqual({ a: 10 })
  })

  it('忽略损坏条目', async () => {
    const fake = makeFakeToy({
      h3000: 'not-json',
      latest: '{"v":1,"t":3000,"q":50,"c":0.9,"cf":0,"dims":{}}',
    })
    mountToy(fake)
    const { listCloudArchives } = useToyCloudArchive()
    const list = await listCloudArchives()
    expect(list).toHaveLength(1)
    expect(list[0]!.t).toBe(3000)
  })

  it('清理旧重复数据：内容相同的多条历史仅保留最新，云端删除其余（含分块）', async () => {
    // 模拟旧数据：同一次结果被多次保存产生的重复（无 session_id），时间戳仅毫秒级差异
    const entry = (t: number) =>
      JSON.stringify({ v: 1, t, q: 70, c: 0.21, cf: 0, dims: { a: 10, b: 20, c: 30 } })
    const fake = makeFakeToy({
      h1000: entry(1000),
      h1001: entry(1001),
      h1002: entry(1002),
      latest: entry(1002),
      r1000_0: '{',
      r1001_0: '{',
      r1002_0: '{',
    })
    mountToy(fake)
    const { listCloudArchives } = useToyCloudArchive()
    const list = await listCloudArchives()
    // 只保留最新一份
    expect(list.map((e) => e.t)).toEqual([1002])
    // 云端已清理：旧历史与旧分块被删除，最新份与 latest 指针保留
    expect(fake.store.h1000).toBeUndefined()
    expect(fake.store.h1001).toBeUndefined()
    expect(fake.store.h1002).toBeDefined()
    expect(fake.store.r1000_0).toBeUndefined()
    expect(fake.store.r1001_0).toBeUndefined()
    expect(fake.store.r1002_0).toBeDefined()
    expect(fake.store.latest).toBeDefined()
  })
})

describe('getCloudResult', () => {
  it('缺少分块时返回 null', async () => {
    const fake = makeFakeToy({ r1000_0: '{"a":', h1000: '{"v":1}' })
    mountToy(fake)
    const { getCloudResult } = useToyCloudArchive()
    expect(await getCloudResult(1000)).toBeNull()
  })

  it('非 Toy 环境返回 null', async () => {
    const { getCloudResult } = useToyCloudArchive()
    expect(await getCloudResult(1000)).toBeNull()
  })
})

describe('deleteCloudArchive', () => {
  it('删除历史份、结果分块；若 latest 指向它则一并清理', async () => {
    const entry = JSON.stringify({ v: 1, t: 1000, q: 50, c: 0.9, cf: 0, dims: {} })
    const fake = makeFakeToy({ h1000: entry, r1000_0: '{}', r1000_1: '[]', latest: entry })
    mountToy(fake)
    const { deleteCloudArchive } = useToyCloudArchive()
    expect(await deleteCloudArchive(1000)).toBe(true)
    expect(fake.store.h1000).toBeUndefined()
    expect(fake.store.r1000_0).toBeUndefined()
    expect(fake.store.r1000_1).toBeUndefined()
    expect(fake.store.latest).toBeUndefined()
  })

  it('latest 指向其它时间戳时不误删', async () => {
    const e1 = JSON.stringify({ v: 1, t: 1000, q: 50, c: 0.9, cf: 0, dims: {} })
    const e2 = JSON.stringify({ v: 1, t: 2000, q: 50, c: 0.9, cf: 0, dims: {} })
    const fake = makeFakeToy({ h1000: e1, h2000: e2, latest: e2 })
    mountToy(fake)
    const { deleteCloudArchive } = useToyCloudArchive()
    expect(await deleteCloudArchive(1000)).toBe(true)
    expect(fake.store.h1000).toBeUndefined()
    expect(fake.store.h2000).toBeDefined()
    expect(fake.store.latest).toBe(e2)
  })
})
