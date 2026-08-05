/**
 * 引擎内部类型定义。
 *
 * 移植自 backend/app/question_bank.py（Weight / Question dataclass 与原始 JSON 结构），
 * 用于 Bilibili Toy 静态托管场景：题库数据通过 Vite JSON 导入打包，
 * 不再依赖后端加载。
 *
 * 结构对应关系：
 *   - Question / Weight  → 后端已解析的对象模型
 *   - RawQuestion        → question-bank/v1/questions.json 的元素
 *   - BankIndex*         → question-bank/v1/questions.index.json 的分桶索引结构
 *   - RawDimensionMeta   → question-bank/v1/dimensions.json 的维度元数据
 */

/** 单维权重：Y 与 N 两个作答方向的加权值（-5~5，不同时为 0）。 */
export interface Weight {
  dimension: string
  yes: number
  no: number
}

/** 题目元数据（metadata）：version 必须为正整数，status 需在合法集合内。 */
export interface QuestionMetadata {
  version: number
  status?: string
  [key: string]: unknown
}

/** 已解析的题目对象（对应后端 Question dataclass，含 status / dimensions 属性）。 */
export class Question {
  readonly id: string
  readonly content: string
  readonly type: string
  readonly category: string
  readonly difficulty: string
  readonly tags: string[]
  readonly weights: Weight[]
  readonly metadata: QuestionMetadata

  constructor(
    id: string,
    content: string,
    type: string,
    category: string,
    difficulty: string,
    tags: string[],
    weights: Weight[],
    metadata: QuestionMetadata = { version: 1 },
  ) {
    this.id = id
    this.content = content
    this.type = type
    this.category = category
    this.difficulty = difficulty
    this.tags = tags
    this.weights = weights
    this.metadata = metadata
  }

  /** 题目状态（默认 draft，与后端 Question.status 一致）。 */
  get status(): string {
    return this.metadata.status ?? 'draft'
  }

  /** 该题涉及的全部维度（按 weights 顺序）。 */
  get dimensions(): string[] {
    return this.weights.map((w) => w.dimension)
  }
}

/** 原始题目 JSON 行（questions.json 元素）。 */
export interface RawWeight {
  dimension: string
  yes: number
  no: number
}

export interface RawQuestion {
  id: string
  content: string
  type: string
  category: string
  difficulty: string
  tags: string[]
  weights: RawWeight[]
  metadata: QuestionMetadata
}

/** 分桶索引结构（questions.index.json）。 */
export interface BankIndexFile {
  path: string
  bucket: string
  questions: number
}

export interface BankIndexGroup {
  name: string
  /** dimension | must | experimental（与题库保持一致） */
  type: string
  bucket_size: number
  bucket_count: number
  question_count: number
  files: BankIndexFile[]
}

export interface BankIndex {
  version: number
  description?: string
  generated_at?: string
  total_questions: number
  groups: BankIndexGroup[]
}

/** 维度元数据（dimensions.json v1.6 规范字段，引擎保留原样）。 */
export interface RawDimensionMeta {
  abbr: string
  /** 中文展示名（规范字段） */
  label: string
  description: string
  /** 低分端倾向标签（分值条左端） */
  low_score_label: string
  /** 低分端表现描述 */
  low_score_description: string
  /** 高分端倾向标签（分值条右端） */
  high_score_label: string
  /** 高分端表现描述 */
  high_score_description: string
}

export type RawDimensionsJson = Record<string, RawDimensionMeta>
