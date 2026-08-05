/**
 * session.ts 单元测试：会话状态机。
 *
 * 覆盖：
 *   - 创建 → 逐题取题 → 提交到完成 → 结果 的完整生命周期；
 *   - 修改答案产生 answer_history 且指针不动（对应后端 docs/API.md 修改规则）；
 *   - 未完成时 getResult 抛 409；完成后 nextQuestion 抛 409；
 *   - 存储层可注入：内存实现共享时，新 manager 实例可恢复并继续；
 *   - 默认 localStorage 存储在无 localStorage 环境下优雅降级。
 *
 * 使用 length=10 的短试卷加速测试；题库为正式打包题库。
 */

import { describe, expect, it } from 'vitest'
import {
  SessionError,
  createLocalStorageSessionStore,
  createMemoryStorage,
  createSessionManager,
} from '../session'
import { localTestApi, sessionManager } from '../index'

describe('完整生命周期：创建 → 作答 → 完成 → 结果', () => {
  it('逐题取题与提交直到完成，最后拿到完整结果', async () => {
    const manager = createSessionManager({ storage: createMemoryStorage() })
    const created = await manager.createSession({ length: 10 })
    expect(created.question_count).toBe(10)
    expect(created.session_id.length).toBeGreaterThan(0)

    let answered = 0
    let lastCompleted = false
    for (let i = 0; i < 10; i++) {
      const q = await manager.nextQuestion(created.session_id)
      expect(q.total).toBe(10)
      expect(q.index).toBe(i)
      expect(q.type).toBe('YN')
      expect(q.content.length).toBeGreaterThan(0)
      const resp = await manager.submitAnswer(created.session_id, {
        question_id: q.question_id,
        answer: i % 2 === 0 ? 'Y' : 'N',
        duration: 3,
      })
      expect(resp.status).toBe('ok')
      expect(resp.total).toBe(10)
      expect(resp.answered_count).toBe(i + 1)
      answered = resp.answered_count
      lastCompleted = resp.completed
    }
    expect(answered).toBe(10)
    expect(lastCompleted).toBe(true)

    // 完成后取题抛 409
    await expect(manager.nextQuestion(created.session_id)).rejects.toMatchObject({
      status: 409,
    })

    const result = await manager.getResult(created.session_id)
    expect(result.session_id).toBe(created.session_id)
    expect(result.completed).toBe(true)
    expect(result.answered_count).toBe(10)
    expect(result.total).toBe(10)
    expect(Object.keys(result.dimensions).length).toBeGreaterThan(0)
    for (const d of Object.values(result.dimensions)) {
      expect(d.score).toBeGreaterThanOrEqual(0)
      expect(d.score).toBeLessThanOrEqual(100)
      expect(d.tendency.length).toBeGreaterThan(0)
      expect(d.description.length).toBeGreaterThan(0)
    }
    expect(result.confidence).toBeGreaterThanOrEqual(0)
    expect(Array.isArray(result.conflicts)).toBe(true)
    expect(Array.isArray(result.uncertain_dimensions)).toBe(true)
  })

  it('未完成时 getResult 抛 409', async () => {
    const manager = createSessionManager({ storage: createMemoryStorage() })
    const created = await manager.createSession({ length: 10 })
    const q0 = await manager.nextQuestion(created.session_id)
    await manager.submitAnswer(created.session_id, { question_id: q0.question_id, answer: 'Y' })

    await expect(manager.getResult(created.session_id)).rejects.toMatchObject({

      status: 409,
    })
    // 错误信息包含进度（对应后端文案）
    const err = await manager
      .getResult(created.session_id)
      .then(() => null)
      .catch((e: SessionError) => e)
    expect(err!.message).toContain('1/10')
  })
})

describe('答案修改规则（后端 docs/API.md 语义）', () => {
  it('修改已出现题目的答案：记录 history、指针不动', async () => {
    const manager = createSessionManager({ storage: createMemoryStorage() })
    const created = await manager.createSession({ length: 10 })
    const q0 = await manager.nextQuestion(created.session_id)
    await manager.submitAnswer(created.session_id, { question_id: q0.question_id, answer: 'Y' })
    const q1 = await manager.nextQuestion(created.session_id) // 指针推进后取第二题
    await manager.submitAnswer(created.session_id, { question_id: q1.question_id, answer: 'N' })

    // 回头修改 q0：指针应停在原地（当前题目仍为 index 2 的题）
    const resp = await manager.submitAnswer(created.session_id, {
      question_id: q0.question_id,
      answer: 'N',
    })
    expect(resp.completed).toBe(false)
    expect(resp.answered_count).toBe(2)
    expect(resp.answer_history).toHaveLength(1)
    expect(resp.answer_history![0]).toMatchObject({
      question_id: q0.question_id,
      old_answer: 'Y',
      new_answer: 'N',
    })

    const next = await manager.nextQuestion(created.session_id)
    expect(next.index).toBe(2) // 指针未移动
  })

  it('重复提交相同答案不产生 history', async () => {
    const manager = createSessionManager({ storage: createMemoryStorage() })
    const created = await manager.createSession({ length: 10 })
    const q0 = await manager.nextQuestion(created.session_id)
    await manager.submitAnswer(created.session_id, { question_id: q0.question_id, answer: 'Y' })
    const resp = await manager.submitAnswer(created.session_id, {
      question_id: q0.question_id,
      answer: 'Y',
    })
    expect(resp.answered_count).toBe(1)
    expect(resp.answer_history).toEqual([])
  })

  it('getAnswers 返回当前答案与修改历史', async () => {
    const manager = createSessionManager({ storage: createMemoryStorage() })
    const created = await manager.createSession({ length: 10 })
    const q0 = await manager.nextQuestion(created.session_id)
    await manager.submitAnswer(created.session_id, { question_id: q0.question_id, answer: 'Y' })
    await manager.submitAnswer(created.session_id, { question_id: q0.question_id, answer: 'N' })
    const answers = await manager.getAnswers(created.session_id)
    expect(answers.session_id).toBe(created.session_id)
    expect(answers.answers[q0.question_id]).toBe('N')
    expect(answers.answer_history).toHaveLength(1)
  })
})

describe('错误语义', () => {
  it('会话不存在抛 404', async () => {
    const manager = createSessionManager({ storage: createMemoryStorage() })
    await expect(manager.nextQuestion('no-such-session')).rejects.toMatchObject({
      status: 404,
    })
    await expect(manager.getResult('no-such-session')).rejects.toMatchObject({ status: 404 })
  })

  it('提交不属于本次会话的题目抛 400；非法答案抛 422', async () => {
    const manager = createSessionManager({ storage: createMemoryStorage() })
    const created = await manager.createSession({ length: 10 })
    await manager.nextQuestion(created.session_id)
    await expect(
      manager.submitAnswer(created.session_id, { question_id: 'Q99999', answer: 'Y' }),
    ).rejects.toMatchObject({ status: 400 })
    const q = await manager.nextQuestion(created.session_id)
    await expect(
      manager.submitAnswer(created.session_id, {
        question_id: q.question_id,
        answer: 'X' as 'Y',
      }),
    ).rejects.toMatchObject({ status: 422 })
  })

  it('SessionError 携带 status（与前端 store 的 409 判断对齐）', async () => {
    const manager = createSessionManager({ storage: createMemoryStorage() })
    const created = await manager.createSession({ length: 10 })
    let caught: unknown = null
    try {
      await manager.getResult(created.session_id)
    } catch (e) {
      caught = e
    }
    expect(caught).toBeInstanceOf(SessionError)
    expect((caught as SessionError).status).toBe(409)
  })
})

describe('持久化恢复', () => {
  it('内存存储共享时，新 manager 实例可恢复会话并继续作答', async () => {
    const storage = createMemoryStorage()
    const m1 = createSessionManager({ storage })
    const created = await m1.createSession({ length: 10 })
    const q0 = await m1.nextQuestion(created.session_id)
    await m1.submitAnswer(created.session_id, { question_id: q0.question_id, answer: 'Y' })
    const q1 = await m1.nextQuestion(created.session_id)
    await m1.submitAnswer(created.session_id, { question_id: q1.question_id, answer: 'N' })

    // 模拟刷新页面：新 manager 从同一存储恢复
    const m2 = createSessionManager({ storage })
    const next = await m2.nextQuestion(created.session_id)
    expect(next.index).toBe(2)
    const answers = await m2.getAnswers(created.session_id)
    expect(answers.answers[q0.question_id]).toBe('Y')

    // 恢复后的会话可以继续答完并出结果
    for (let i = 2; i < 10; i++) {
      const q = await m2.nextQuestion(created.session_id)
      await m2.submitAnswer(created.session_id, { question_id: q.question_id, answer: 'Y' })
    }
    const result = await m2.getResult(created.session_id)
    expect(result.completed).toBe(true)
    expect(result.answered_count).toBe(10)
  })
})

describe('localStorage 默认存储', () => {
  it('无 localStorage 环境（Node）下读写不抛错（优雅降级）', () => {
    const store = createLocalStorageSessionStore()
    expect(store.load()).toBeNull()
    expect(() => store.save({})).not.toThrow()
    expect(() => store.load()).not.toThrow()
  })
})

describe('localTestApi 门面', () => {
  it('health / getDimensions / getPrivacy 返回对齐结构', async () => {
    const health = await localTestApi.health()
    expect(health.status).toBe('ok')
    expect(health.question_bank_version).toBe('v1')
    expect(health.groups).toBe(12)
    expect(health.active_questions).toBe(500)

    const dims = await localTestApi.getDimensions()
    expect(Object.keys(dims)).toHaveLength(10)
    expect(dims['freedom']).toMatchObject({ name: '自由需求' })

    const privacy = await localTestApi.getPrivacy()
    expect(privacy.version).toBe('1.0')
    expect(privacy.retention.session_ttl_days).toBeGreaterThan(0)
    expect(privacy.sections.length).toBeGreaterThan(0)
    expect(privacy.sections[0]!.title.length).toBeGreaterThan(0)
  })

  it('createSession/nextQuestion/submitAnswer/getResult 走本地会话管理器', async () => {
    const created = await sessionManager.createSession({ length: 10 })
    const q = await sessionManager.nextQuestion(created.session_id)
    const resp = await sessionManager.submitAnswer(created.session_id, {
      question_id: q.question_id,
      answer: 'Y',
    })
    expect(resp.status).toBe('ok')
    await expect(sessionManager.getResult(created.session_id)).rejects.toMatchObject({
      status: 409,
    })
  })
})

describe('getSessionInfo（本地探活，供恢复进度用）', () => {
  it('会话存在且进行中时返回 total/completed=false', async () => {
    const manager = createSessionManager({ storage: createMemoryStorage() })
    const created = await manager.createSession({ length: 10 })
    const info = manager.getSessionInfo(created.session_id)
    expect(info).toEqual({ total: 10, completed: false })
  })

  it('完成后返回 completed=true', async () => {
    const manager = createSessionManager({ storage: createMemoryStorage() })
    const created = await manager.createSession({ length: 10 })
    for (let i = 0; i < 10; i++) {
      const q = await manager.nextQuestion(created.session_id)
      await manager.submitAnswer(created.session_id, { question_id: q.question_id, answer: 'Y' })
    }
    expect(manager.getSessionInfo(created.session_id)).toEqual({
      total: 10,
      completed: true,
    })
  })

  it('会话不存在时返回 null', () => {
    const manager = createSessionManager({ storage: createMemoryStorage() })
    expect(manager.getSessionInfo('nonexistent')).toBeNull()
  })

  it('新 manager 实例（共享存储）可探活恢复的会话', async () => {
    const storage = createMemoryStorage()
    const m1 = createSessionManager({ storage })
    const created = await m1.createSession({ length: 10 })
    const m2 = createSessionManager({ storage })
    expect(m2.getSessionInfo(created.session_id)).toEqual({
      total: 10,
      completed: false,
    })
  })
})
