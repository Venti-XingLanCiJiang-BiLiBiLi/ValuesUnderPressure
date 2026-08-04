/**
 * 与后端 REST API 对齐的类型定义
 * 详见 backend/app/schemas.py 与 docs/API.md
 */

export type AnswerValue = 'Y' | 'N'

export interface CreateSessionRequest {
  length?: number
  dimensions?: string[] | null
}

export interface CreateSessionResponse {
  session_id: string
  question_count: number
}

export interface QuestionResponse {
  question_id: string
  content: string
  type: 'YN' | string
  index: number
  total: number
}

export interface SubmitAnswerRequest {
  question_id: string
  answer: AnswerValue
  duration?: number
}

export interface AnswerHistoryEntry {
  question_id: string
  old_answer: string
  new_answer: string
  changed_at: string
}

export interface SubmitAnswerResponse {
  status: string
  answered_count: number
  total: number
  completed: boolean
  answer_history?: AnswerHistoryEntry[]
}

export interface AnswersResponse {
  session_id: string
  answers: Record<string, AnswerValue>
  answer_history: AnswerHistoryEntry[]
}

export interface DimensionScore {
  dimension: string
  name: string
  score: number
  tendency: string
  description: string
  consistency: number | null
  question_count: number
  /** 维度级可信度 0~1；旧存档可能缺失，消费时请用 `?? 0` 兜底 */
  confidence?: number
}

export interface ConflictItem {
  dimensions: [string, string]
  names: [string, string]
  description: string
}

export interface ResultResponse {
  session_id: string
  completed: boolean
  answered_count: number
  total: number
  dimensions: Record<string, DimensionScore>
  /** 整体置信度 0~1；旧存档可能缺失，消费时请用 `?? 0` 兜底 */
  confidence?: number
  conflicts: ConflictItem[]
  uncertain_dimensions: string[]
}

export interface DimensionMeta {
  name: string
  description: string
  direction: [string, string]
}

export interface HealthResponse {
  status: string
  /** 题库版本（如 v1），对应 question-bank/<版本>/ 目录 */
  question_bank_version: string
  /** 分桶索引组数（维度组 + must + experimental） */
  groups: number
  /** 当前题库版本总题数（来自分桶索引） */
  active_questions: number
}

/** 隐私政策：一个章节（标题 + 正文，正文用 \n 分段） */
export interface PrivacySection {
  title: string
  body: string
}

/** 服务端数据保留期（天），由后端按运行期配置返回 */
export interface PrivacyRetention {
  session_ttl_days: number
  completed_session_ttl_days: number
}

export interface PrivacyResponse {
  version: string
  effective_date: string
  retention: PrivacyRetention
  sections: PrivacySection[]
}
