import axios, { type AxiosError, type AxiosInstance } from 'axios'
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

/**
 * Axios 实例
 * - 开发环境：baseURL 走 Vite proxy (/api → http://127.0.0.1:8000)
 * - 生产环境：使用 import.meta.env.VITE_API_BASE_URL（部署时由 CI 注入）
 *            默认 '/api'，意味着前端和后端部署在同源（通过 nginx/cloudflare 等反代）
 *            部署到 GitHub Pages（静态托管）时，需在 CI 中设为后端公网 URL，例如：
 *              VITE_API_BASE_URL=https://api.your-domain.com/api
 */
const http: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// 统一错误：把后端 message 提取出来
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

http.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<{ detail?: string | { msg: string }[] }>) => {
    const status = error.response?.status ?? 0
    const payload = error.response?.data
    let message = error.message
    if (payload) {
      if (typeof payload.detail === 'string') {
        message = payload.detail
      } else if (Array.isArray(payload.detail) && payload.detail[0]?.msg) {
        message = payload.detail[0].msg
      }
    }
    return Promise.reject(new ApiError(message, status, payload))
  },
)

/**
 * 带指数退避的请求重试（#20）
 * ============================================================================
 * - 仅对「网络层错误」重试：超时 / 断连 / 无 HTTP 响应
 *   （拦截器已把 axios 错误转成 ApiError，此时 status === 0）。
 * - 业务错误（4xx/5xx，status !== 0，如 404/409/422）不重试，
 *   避免无意义地重复提交或掩盖业务语义。
 * - 默认最多重试 3 次，退避 1s → 2s → 4s。
 * ============================================================================
 */
async function requestWithRetry<T>(
  fn: () => Promise<T>,
  retries = 3,
  delay = 1000,
): Promise<T> {
  try {
    return await fn()
  } catch (e) {
    const retriable = e instanceof ApiError && e.status === 0
    if (retries <= 0 || !retriable) throw e
    await new Promise((r) => setTimeout(r, delay))
    return requestWithRetry(fn, retries - 1, delay * 2)
  }
}

export const testApi = {
  async health(): Promise<HealthResponse> {
    return requestWithRetry(async () => {
      const { data } = await http.get<HealthResponse>('/health')
      return data
    })
  },

  async getDimensions(): Promise<Record<string, DimensionMeta>> {
    return requestWithRetry(async () => {
      const { data } = await http.get<Record<string, DimensionMeta>>('/dimensions')
      return data
    })
  },

  /** 拉取隐私政策（含实际保留期），供 /privacy 页展示。 */
  async getPrivacy(): Promise<PrivacyResponse> {
    return requestWithRetry(async () => {
      const { data } = await http.get<PrivacyResponse>('/meta/privacy')
      return data
    })
  },

  async createSession(req: CreateSessionRequest = {}): Promise<CreateSessionResponse> {
    return requestWithRetry(async () => {
      const { data } = await http.post<CreateSessionResponse>('/test/session', {
        length: req.length ?? 40,
        dimensions: req.dimensions ?? null,
      })
      return data
    })
  },

  async nextQuestion(sessionId: string): Promise<QuestionResponse> {
    return requestWithRetry(async () => {
      const { data } = await http.get<QuestionResponse>(`/test/session/${sessionId}/question`)
      return data
    })
  },

  async submitAnswer(sessionId: string, req: SubmitAnswerRequest): Promise<SubmitAnswerResponse> {
    // 提交属写操作：网络波动时重试 2 次（退避 1s → 2s）；业务错误不重试
    return requestWithRetry(
      async () => {
        const { data } = await http.post<SubmitAnswerResponse>(
          `/test/session/${sessionId}/answer`,
          req,
        )
        return data
      },
      2,
    )
  },

  async getResult(sessionId: string): Promise<ResultResponse> {
    return requestWithRetry(async () => {
      const { data } = await http.get<ResultResponse>(`/test/session/${sessionId}/result`)
      return data
    })
  },
}
