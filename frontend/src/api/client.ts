import axios, { type AxiosError, type AxiosInstance } from 'axios'
import type {
  CreateSessionRequest,
  CreateSessionResponse,
  DimensionMeta,
  HealthResponse,
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

export const testApi = {
  async health(): Promise<HealthResponse> {
    const { data } = await http.get<HealthResponse>('/health')
    return data
  },

  async getDimensions(): Promise<Record<string, DimensionMeta>> {
    const { data } = await http.get<Record<string, DimensionMeta>>('/dimensions')
    return data
  },

  async createSession(req: CreateSessionRequest = {}): Promise<CreateSessionResponse> {
    const { data } = await http.post<CreateSessionResponse>('/test/session', {
      length: req.length ?? 40,
      dimensions: req.dimensions ?? null,
    })
    return data
  },

  async nextQuestion(sessionId: string): Promise<QuestionResponse> {
    const { data } = await http.get<QuestionResponse>(`/test/session/${sessionId}/question`)
    return data
  },

  async submitAnswer(sessionId: string, req: SubmitAnswerRequest): Promise<SubmitAnswerResponse> {
    const { data } = await http.post<SubmitAnswerResponse>(
      `/test/session/${sessionId}/answer`,
      req,
    )
    return data
  },

  async getResult(sessionId: string): Promise<ResultResponse> {
    const { data } = await http.get<ResultResponse>(`/test/session/${sessionId}/result`)
    return data
  },
}
