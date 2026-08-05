import type {
  CreateSessionRequest,
  CreateSessionResponse,
  DimensionMeta,
  HealthResponse,
  PrivacyResponse,
  QuestionResponse,
  ResultResponse,
  SubmitAnswerRequest,
  SubmitAnswerResponse,
} from '@/types/api'
import { localTestApi } from '@/engine'
import { SessionError } from '@/engine/session'

/**
 * 本地引擎 API 门面（替代原 axios REST 客户端）
 * ============================================================================
 * Toy 静态托管没有后端，所有「API」改由本地引擎（frontend/src/engine/）承担：
 * 组卷、计分、会话状态机全部在浏览器内完成。
 *
 * - 方法签名与原 axios 版 testApi 完全一致，调用方（stores / views）无需改动；
 * - 保留 ApiError 语义：引擎抛出的 SessionError 统一转换为 ApiError
 *   （status / message），让现有 `e instanceof ApiError && e.status === 409`
 *   之类的判断继续生效；
 * - 无网络错误（status 0）场景，故原 requestWithRetry 重试逻辑不再需要。
 * ============================================================================
 */

export class ApiError extends Error {
  status: number
  data: unknown
  constructor(message: string, status: number, data: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

/** 把引擎错误统一转换为 ApiError，保持调用方错误处理不变。 */
async function adapt<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn()
  } catch (e) {
    if (e instanceof SessionError) {
      throw new ApiError(e.message, e.status, e)
    }
    throw e
  }
}

export const testApi = {
  async health(): Promise<HealthResponse> {
    return adapt(() => localTestApi.health())
  },

  async getDimensions(): Promise<Record<string, DimensionMeta>> {
    return adapt(() => localTestApi.getDimensions())
  },

  async getPrivacy(): Promise<PrivacyResponse> {
    return adapt(() => localTestApi.getPrivacy())
  },

  async createSession(
    req: CreateSessionRequest = {},
  ): Promise<CreateSessionResponse> {
    return adapt(() => localTestApi.createSession(req))
  },

  async nextQuestion(sessionId: string): Promise<QuestionResponse> {
    return adapt(() => localTestApi.nextQuestion(sessionId))
  },

  async submitAnswer(
    sessionId: string,
    req: SubmitAnswerRequest,
  ): Promise<SubmitAnswerResponse> {
    return adapt(() => localTestApi.submitAnswer(sessionId, req))
  },

  async getResult(sessionId: string): Promise<ResultResponse> {
    return adapt(() => localTestApi.getResult(sessionId))
  },
}
