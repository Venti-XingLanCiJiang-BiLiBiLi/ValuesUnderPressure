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

export interface SubmitAnswerResponse {
  status: string
  answered_count: number
  total: number
  completed: boolean
}

export interface DimensionScore {
  dimension: string
  name: string
  score: number
  tendency: string
  description: string
  consistency: number | null
  question_count: number
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
  confidence: number
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
  question_bank_source: string
  active_questions: number
  invalid_questions: number
}
