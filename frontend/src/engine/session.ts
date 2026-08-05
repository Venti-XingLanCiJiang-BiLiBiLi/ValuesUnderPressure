/**
 * 本地会话状态机（移植自 backend/app/routers/sessions.py 与会话语义）。
 *
 * 静态托管场景下没有后端 DB，会话状态在内存中维护，并通过可注入的
 * 存储层持久化（默认 localStorage，key: `quxu:engine:sessions`，
 * 读写带 try/catch 降级；测试可注入内存实现）。
 *
 * 语义与后端一致：
 *   - createSession: buildTest 生成试卷（seed 用 Date.now()），
 *     sessionId 用 crypto.randomUUID()；
 *   - nextQuestion: 顺序作答指针 current_index 指向的题目，指针越过末尾抛 409；
 *   - submitAnswer: 顺序作答指针前移；对已出现题目的修改不移动指针；
 *     旧答案不同时记录 answer_history；completed = 指针越过末尾；
 *   - getResult: 结果必须完整作答，否则抛 409。
 * 错误类 SessionError 携带 status，与前端 store 的 err.status === 409 判断对齐。
 */

import type {
  AnswerHistoryEntry,
  AnswerValue,
  AnswersResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  QuestionResponse,
  ResultResponse,
  SubmitAnswerRequest,
  SubmitAnswerResponse,
} from '../types/api'
import { bank, type BucketBank } from './bank'
import { scoreSession, toApiDimension } from './scoring'
import { buildTest, DEFAULT_LENGTH } from './selection'
import type { Question } from './types'

/** 会话存储 key（默认 localStorage 键名）。 */
export const SESSION_STORAGE_KEY = 'quxu:engine:sessions'

/** 携带 HTTP 状态码的引擎错误（409 = 已完成/未完成，404 = 会话不存在）。 */
export class SessionError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'SessionError'
    this.status = status
  }
}

/** 持久化的会话数据（对应后端 test_sessions + answers + answer_history）。 */
export interface StoredSession {
  session_id: string
  question_ids: string[]
  current_index: number
  answers: Record<string, AnswerValue>
  answer_history: AnswerHistoryEntry[]
  created_at: string
  status: 'in_progress' | 'completed'
}

/** 存储层接口（可注入：默认 localStorage，测试传内存实现）。 */
export interface SessionStorage {
  load(): Record<string, StoredSession> | null
  save(sessions: Record<string, StoredSession>): void
}

/** 内存存储（测试用；跨 manager 实例共享同一对象即可模拟持久化恢复）。 */
export function createMemoryStorage(): SessionStorage {
  let data: Record<string, StoredSession> | null = null
  return {
    load() {
      return data
    },
    save(sessions) {
      data = sessions
    },
  }
}

/**
 * localStorage 存储（默认实现）：读写带 try/catch 降级，
 * 环境不支持（如 Node 无 jsdom / 隐私模式）时静默退化为不持久化。
 */
export function createLocalStorageSessionStore(
  key = SESSION_STORAGE_KEY,
): SessionStorage {
  return {
    load() {
      try {
        const raw = globalThis.localStorage?.getItem(key)
        if (!raw) return null
        const parsed = JSON.parse(raw) as Record<string, StoredSession>
        return parsed && typeof parsed === 'object' ? parsed : null
      } catch {
        return null
      }
    },
    save(sessions) {
      try {
        globalThis.localStorage?.setItem(key, JSON.stringify(sessions))
      } catch {
        // 忽略（隐私模式 / 存储满等）
      }
    },
  }
}

export interface SessionManagerOptions {
  storage?: SessionStorage
  bank?: BucketBank
}

/** 会话恢复所需的元信息（本地探活，替代原后端 GET /question 探活）。 */
export interface SessionInfo {
  total: number
  completed: boolean
}

/** 会话状态机入口（与后端 sessions.py 路由一一对应）。 */
export interface SessionManager {
  createSession(req?: CreateSessionRequest): Promise<CreateSessionResponse>
  nextQuestion(sessionId: string): Promise<QuestionResponse>
  submitAnswer(
    sessionId: string,
    req: SubmitAnswerRequest,
  ): Promise<SubmitAnswerResponse>
  getAnswers(sessionId: string): Promise<AnswersResponse>
  getResult(sessionId: string): Promise<ResultResponse>
  /** 本地探活：按 id 读会话元信息；会话不存在时返回 null。 */
  getSessionInfo(sessionId: string): SessionInfo | null
}

export function createSessionManager(
  options: SessionManagerOptions = {},
): SessionManager {
  const storage: SessionStorage =
    options.storage ?? createLocalStorageSessionStore()
  const engineBank: BucketBank = options.bank ?? bank
  let sessions: Record<string, StoredSession> = storage.load() ?? {}

  function persist(): void {
    storage.save(sessions)
  }

  /** 对应后端 _session_or_404。 */
  function sessionOr404(sessionId: string): StoredSession {
    const session = sessions[sessionId]
    if (!session) {
      throw new SessionError('测试会话不存在', 404)
    }
    return session
  }

  /** 对应后端 _session_questions：按 id 取题，缺失的题目跳过。 */
  function sessionQuestions(session: StoredSession): Question[] {
    const qs: Question[] = []
    for (const qid of session.question_ids) {
      const q = engineBank.get(qid)
      if (q !== null) {
        qs.push(q)
      }
    }
    return qs
  }

  return {
    async createSession(req: CreateSessionRequest = {}) {
      const length = req.length ?? DEFAULT_LENGTH
      const questions = buildTest(engineBank, {
        length,
        dimensions: req.dimensions ?? undefined,
        seed: Date.now(),
      })
      if (questions.length === 0) {
        throw new SessionError('题库为空或无法生成试卷，请检查题库文件', 500)
      }
      const sessionId = crypto.randomUUID()
      sessions[sessionId] = {
        session_id: sessionId,
        question_ids: questions.map((q) => q.id),
        current_index: 0,
        answers: {},
        answer_history: [],
        created_at: new Date().toISOString(),
        status: 'in_progress',
      }
      persist()
      return { session_id: sessionId, question_count: questions.length }
    },

    async nextQuestion(sessionId: string): Promise<QuestionResponse> {
      const session = sessionOr404(sessionId)
      const questions = sessionQuestions(session)
      const idx = session.current_index

      if (idx >= questions.length) {
        throw new SessionError('本次测试已完成，请调用结果接口', 409)
      }

      const q = questions[idx]!
      return {
        question_id: q.id,
        content: q.content,
        type: q.type,
        index: idx,
        total: questions.length,
      }
    },

    async submitAnswer(
      sessionId: string,
      req: SubmitAnswerRequest,
    ): Promise<SubmitAnswerResponse> {
      const session = sessionOr404(sessionId)
      const questions = sessionQuestions(session)
      const ids = questions.map((q) => q.id)

      if (!ids.includes(req.question_id)) {
        throw new SessionError('question_id 不属于本次测试会话', 400)
      }
      if (req.answer !== 'Y' && req.answer !== 'N') {
        throw new SessionError("answer 只能为 'Y' 或 'N'", 422)
      }

      const idx = session.current_index
      let newIdx: number
      if (idx < questions.length && questions[idx]!.id === req.question_id) {
        // 正常顺序作答，指针前移
        newIdx = idx + 1
      } else {
        // 允许对已出现过的题目进行补答/修改，不移动指针
        newIdx = idx
      }

      // 允许修改已提交的答案（价值观测试不是考试）：
      // 修改不改变答题进度，但必须记录修改历史 answer_history。
      const oldAnswer = session.answers[req.question_id]
      session.answers[req.question_id] = req.answer
      if (oldAnswer !== undefined && oldAnswer !== req.answer) {
        session.answer_history.push({
          question_id: req.question_id,
          old_answer: oldAnswer,
          new_answer: req.answer,
          changed_at: new Date().toISOString(),
        })
      }

      session.current_index = newIdx
      const answeredCount = Object.keys(session.answers).length
      const completed = newIdx >= questions.length
      if (completed) {
        session.status = 'completed'
      }
      persist()

      return {
        status: 'ok',
        answered_count: answeredCount,
        total: questions.length,
        completed,
        answer_history: session.answer_history.map((h) => ({ ...h })),
      }
    },

    async getAnswers(sessionId: string): Promise<AnswersResponse> {
      const session = sessionOr404(sessionId)
      return {
        session_id: sessionId,
        answers: { ...session.answers },
        answer_history: session.answer_history.map((h) => ({ ...h })),
      }
    },

    getSessionInfo(sessionId: string): SessionInfo | null {
      const session = sessions[sessionId]
      if (!session) return null
      return {
        total: session.question_ids.length,
        completed: session.status === 'completed',
      }
    },

    async getResult(sessionId: string): Promise<ResultResponse> {
      const session = sessionOr404(sessionId)
      const questions = sessionQuestions(session)
      const answers = session.answers
      // 结果必须基于完整作答：未完成全部题目时返回 409，避免把部分作答
      // 当作完整画像输出（归一化、一致性都需要完整样本才有效）。
      if (Object.keys(answers).length < questions.length) {
        throw new SessionError(
          `测试尚未完成：已作答 ${Object.keys(answers).length}/${questions.length}，` +
            '请完成所有题目后再获取结果',
          409,
        )
      }

      const result = scoreSession(questions, answers)
      const dimensionPayload: ResultResponse['dimensions'] = {}
      for (const [dim, r] of Object.entries(result.dimensions)) {
        dimensionPayload[dim] = toApiDimension(r)
      }

      return {
        session_id: sessionId,
        completed: Object.keys(answers).length >= questions.length,
        answered_count: Object.keys(answers).length,
        total: questions.length,
        dimensions: dimensionPayload,
        confidence: result.confidence,
        conflicts: result.conflicts,
        uncertain_dimensions: result.uncertain_dimensions,
      }
    },
  }
}
