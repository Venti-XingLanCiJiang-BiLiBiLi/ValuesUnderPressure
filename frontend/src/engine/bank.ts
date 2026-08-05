/**
 * 题库加载与校验模块（移植自 backend/app/question_bank.py）。
 *
 * 静态托管场景下没有后端文件系统，题库直接通过 Vite JSON 导入打包：
 *   - questions.json      500 题合并题库（按 id 升序 Q00001..Q00500）
 *   - questions.index.json 分桶索引（groups[] 结构记录）
 *   - dimensions.json     维度元数据（用于校验维度合法性）
 *
 * BucketBank 与后端一致按分桶索引懒加载桶，但桶成员改为从合并题库
 * 内存重建（不读磁盘桶文件）。重建算法（已验证与真实桶文件完全一致）：
 *   - dimension 组：`weights[0].dimension === name` 且 category 不属于特殊组
 *     （must / experimental）的题目；按 `weights[0].yes` 分组、组内按 id 升序，
 *     每 4 题切成一块；块按分桶索引 files 顺序对应（freedom 每主权重桶
 *     8 题切成 2 块，即每块 4 题）；
 *   - must / experimental 组：`category === name` 的题目按 id 升序，
 *     按 files 顺序与每文件 questions 数切块。
 * 注意：dimension 组必须排除特殊组题目（Q0044x~Q00500 的主维度属于
 * 各常规维度，但归属 must / experimental 桶）。
 */

import rawQuestionsJson from '../../../question-bank/v1/questions.json'
import rawIndexJson from '../../../question-bank/v1/questions.index.json'
import rawDimensionsJson from '../../../question-bank/v1/dimensions.json'
import type {
  BankIndex,
  BankIndexGroup,
  QuestionMetadata,
  RawDimensionMeta,
  RawDimensionsJson,
  RawQuestion,
  RawWeight,
  Weight,
} from './types'
import { Question } from './types'

/** 当前打包的题库版本（对应 question-bank/<version>/ 目录名）。 */
export const BANK_VERSION = 'v1'

export const VALID_DIFFICULTY = ['easy', 'medium', 'hard'] as const
export const VALID_STATUS = ['draft', 'active', 'experimental', 'deprecated'] as const

/** 合法维度集合（来自 dimensions.json，与后端 DIMENSION_IDS 对齐）。 */
export const DIMENSION_IDS: string[] = Object.keys(
  rawDimensionsJson as unknown as RawDimensionsJson,
)

const RAW_QUESTIONS = rawQuestionsJson as unknown as RawQuestion[]
const RAW_INDEX = rawIndexJson as unknown as BankIndex

const RAW_DIMENSIONS: RawDimensionsJson =
  rawDimensionsJson as unknown as RawDimensionsJson

/**
 * 对单条原始题目做 schema/权重/内容层面的校验，返回问题列表（不抛异常）。
 * 移植自 backend/app/question_bank.py `_validate_raw`。
 */
export function validateRawQuestion(
  raw: RawQuestion,
  seenIds: Set<string>,
): string[] {
  const errors: string[] = []
  const qid = raw.id
  if (!qid) {
    errors.push('缺少 id')
  } else if (seenIds.has(qid)) {
    errors.push(`id 重复: ${qid}`)
  }

  if (!raw.content) {
    errors.push(`[${qid}] content 不能为空`)
  }

  if (raw.type !== 'YN') {
    errors.push(`[${qid}] type 必须为 YN`)
  }

  if (!VALID_DIFFICULTY.includes(raw.difficulty as (typeof VALID_DIFFICULTY)[number])) {
    errors.push(`[${qid}] difficulty 非法: ${raw.difficulty}`)
  }

  const weights = raw.weights ?? []
  if (!weights.length) {
    errors.push(`[${qid}] weights 至少包含一个维度`)
  }

  const seenDims = new Set<string>()
  for (const w of weights) {
    const dim = w.dimension
    const yes = w.yes
    const no = w.no
    if (!DIMENSION_IDS.includes(dim)) {
      errors.push(`[${qid}] 未知维度: ${dim}`)
    }
    if (seenDims.has(dim)) {
      errors.push(`[${qid}] 维度重复: ${dim}`)
    }
    seenDims.add(dim)
    for (const [val, name] of [
      [yes, 'yes'],
      [no, 'no'],
    ] as const) {
      if (typeof val !== 'number' || !Number.isInteger(val) || val < -5 || val > 5) {
        errors.push(`[${qid}] 权重 ${name} 超出 -5~5 范围: ${val}`)
      }
    }
    if (yes === 0 && no === 0) {
      errors.push(`[${qid}] yes 和 no 不能同时为 0`)
    }
  }

  const metadata = raw.metadata ?? {}
  const version = metadata.version
  if (typeof version !== 'number' || !Number.isInteger(version) || version < 1) {
    errors.push(`[${qid}] metadata.version 必须为正整数`)
  }
  if (metadata.status !== undefined && !VALID_STATUS.includes(metadata.status as (typeof VALID_STATUS)[number])) {
    errors.push(`[${qid}] metadata.status 非法: ${metadata.status}`)
  }

  return errors
}

/**
 * 把单条原始题目转换为 Question 对象；字段非法时返回 null。
 * 移植自 backend/app/question_bank.py `_to_question`。
 */
export function toQuestion(raw: RawQuestion): Question | null {
  if (!raw.weights || raw.weights.length === 0) {
    return null
  }
  try {
    return new Question(
      raw.id,
      raw.content,
      raw.type,
      raw.category ?? '',
      raw.difficulty ?? '',
      raw.tags ?? [],
      raw.weights.map((w) => toWeight(w)),
      (raw.metadata ?? {}) as QuestionMetadata,
    )
  } catch {
    return null
  }
}

function toWeight(raw: RawWeight): Weight {
  return { dimension: raw.dimension, yes: raw.yes, no: raw.no }
}

/** 按 id 升序比较原始题目。 */
function byIdAsc(a: RawQuestion, b: RawQuestion): number {
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0
}

/**
 * 从全量题库列表构建虚拟分桶索引（无 index 文件时的开发/测试回退，
 * 对应后端 build_virtual_index；桶 path 为 `__mem__/<dim>/<idx>`）。
 */
export function buildVirtualIndex(
  rawList: RawQuestion[],
  bucketSize = 4,
): BankIndex {
  const groups = new Map<string, RawQuestion[]>()
  for (const raw of rawList) {
    if (!raw.weights || raw.weights.length === 0) {
      continue
    }
    const primary = raw.weights[0].dimension ?? 'unknown'
    const list = groups.get(primary) ?? []
    list.push(raw)
    groups.set(primary, list)
  }

  const indexGroups: BankIndexGroup[] = []
  for (const [dim, raws] of groups) {
    raws.sort(byIdAsc)
    const files = []
    for (let i = 0; i < raws.length; i += bucketSize) {
      const idx = i / bucketSize
      files.push({
        path: `__mem__/${dim}/${idx}`,
        bucket: String(idx + 1),
        questions: raws.slice(i, i + bucketSize).length,
      })
    }
    indexGroups.push({
      name: dim,
      type: 'dimension',
      bucket_size: bucketSize,
      bucket_count: files.length,
      question_count: raws.length,
      files,
    })
  }

  return {
    version: 1,
    description: '虚拟分桶索引（由全量题库构建，开发/测试回退用）',
    total_questions: rawList.length,
    groups: indexGroups,
  }
}

/**
 * 基于分桶索引的题库访问（抽题主数据源，对应后端 BucketBank）。
 *
 * 与后端不同：桶成员由合并题库 + 分桶索引内存重建（见文件顶部算法说明），
 * loadBucket 从内存返回，不再读磁盘桶文件。
 */
export class BucketBank {
  readonly index: BankIndex
  /** 版本名（对应 question-bank/<version>/ 目录，供 version() 返回）。 */
  readonly baseDir: string

  private _bucketCache = new Map<string, Question[]>()
  private _groupCache = new Map<string, Question[]>()
  private _memBuckets = new Map<string, RawQuestion[]>()
  private _byId = new Map<string, Question>()
  /** 加载时校验失败的问题记录（不阻断启动，对应后端 invalid 列表）。 */
  readonly invalid: string[] = []

  constructor(
    index: BankIndex,
    baseDir = '1',
    options?: { rawList?: RawQuestion[]; memBuckets?: Map<string, RawQuestion[]> },
  ) {
    this.index = index
    this.baseDir = baseDir
    if (options?.rawList) {
      this._rebuildBuckets(options.rawList)
    } else if (options?.memBuckets) {
      this._memBuckets = options.memBuckets
    }
  }

  /** 从合并题库 + 分桶索引构建正式 BucketBank（校验 + 重建桶）。 */
  static load(): BucketBank {
    const seenIds = new Set<string>()
    const questions: RawQuestion[] = []
    const invalid: string[] = []
    for (const raw of RAW_QUESTIONS) {
      const errors = validateRawQuestion(raw, seenIds)
      if (errors.length > 0) {
        invalid.push(...errors)
        continue
      }
      seenIds.add(raw.id)
      questions.push(raw)
    }
    const bank = new BucketBank(RAW_INDEX, BANK_VERSION)
    bank.invalid.push(...invalid)
    bank._rebuildBuckets(questions)
    bank._checkIndexConsistency()
    return bank
  }

  /** 从全量题目列表构建虚拟 BucketBank（测试用，对应后端 from_questions）。 */
  static fromQuestions(rawList: RawQuestion[], bucketSize = 4): BucketBank {
    const index = buildVirtualIndex(rawList, bucketSize)
    const bank = new BucketBank(index, '')
    // 虚拟桶与后端一致：按主维度过滤 + id 升序，按整组顺序切桶
    // （桶的 bucket 字段是块序号而非权重桶号，不能用 _rebuildDimensionGroup）。
    for (const group of index.groups) {
      const chunk = rawList
        .filter((r) => r.weights.length > 0 && r.weights[0].dimension === group.name)
        .sort(byIdAsc)
      for (const f of group.files) {
        const start = (Number(f.bucket) - 1) * bucketSize
        bank._memBuckets.set(f.path, chunk.slice(start, start + bucketSize))
      }
    }
    return bank
  }

  // ------------------------------------------------------------------
  // 桶重建
  // ------------------------------------------------------------------
  private _rebuildBuckets(rawList: RawQuestion[]): void {
    // 特殊组（type !== 'dimension'，如 must / experimental）的名称集合，
    // 其题目不参与任何常规维度桶。
    const specialCategories = new Set(
      this.index.groups
        .filter((g) => g.type !== 'dimension')
        .map((g) => g.name),
    )

    for (const group of this.index.groups) {
      if (group.type === 'dimension') {
        this._rebuildDimensionGroup(group, rawList, specialCategories)
      } else {
        this._rebuildCategoryGroup(group, rawList)
      }
    }
  }

  private _rebuildDimensionGroup(
    group: BankIndexGroup,
    rawList: RawQuestion[],
    specialCategories: Set<string>,
  ): void {
    const members = rawList.filter(
      (q) =>
        q.weights.length > 0 &&
        q.weights[0].dimension === group.name &&
        !specialCategories.has(q.category),
    )
    // 按主权重 yes 分组，组间按桶字符串字典序（对应索引 files 顺序：-1..-5,1..5）
    const byYes = new Map<number, RawQuestion[]>()
    for (const q of members) {
      const yes = q.weights[0].yes
      const list = byYes.get(yes) ?? []
      list.push(q)
      byYes.set(yes, list)
    }
    const consumed = new Map<number, number>()
    for (const f of group.files) {
      const yes = Number(f.bucket)
      const list = byYes.get(yes)
      const start = consumed.get(yes) ?? 0
      const chunk = list
        ? list.sort(byIdAsc).slice(start, start + f.questions)
        : []
      consumed.set(yes, start + f.questions)
      this._memBuckets.set(f.path, chunk)
    }
  }

  private _rebuildCategoryGroup(group: BankIndexGroup, rawList: RawQuestion[]): void {
    const members = rawList.filter((q) => q.category === group.name)
    members.sort(byIdAsc)
    let offset = 0
    for (const f of group.files) {
      this._memBuckets.set(f.path, members.slice(offset, offset + f.questions))
      offset += f.questions
    }
  }

  /** 校验重建结果与索引的一致性（不抛错，记录到 invalid）。 */
  private _checkIndexConsistency(): void {
    let total = 0
    for (const group of this.index.groups) {
      total += group.question_count
      if (group.files.length !== group.bucket_count) {
        this.invalid.push(
          `组 ${group.name} 桶数不一致: index=${group.bucket_count} files=${group.files.length}`,
        )
      }
      const fileSum = group.files.reduce((s, f) => s + f.questions, 0)
      if (fileSum !== group.question_count) {
        this.invalid.push(
          `组 ${group.name} 题数不一致: index=${group.question_count} files=${fileSum}`,
        )
      }
    }
    if (total !== this.index.total_questions) {
      this.invalid.push(
        `索引总题数不一致: index=${this.index.total_questions} 组总和=${total}`,
      )
    }
  }

  // ------------------------------------------------------------------
  // 索引访问
  // ------------------------------------------------------------------
  groups(): BankIndexGroup[] {
    return this.index.groups
  }

  group(name: string): BankIndexGroup | null {
    return this.index.groups.find((g) => g.name === name) ?? null
  }

  totalQuestions(): number {
    return this.index.total_questions
  }

  version(): string {
    return this.baseDir || '1'
  }

  // ------------------------------------------------------------------
  // 桶 / 组懒加载
  // ------------------------------------------------------------------
  loadBucket(relPath: string): Question[] {
    const cached = this._bucketCache.get(relPath)
    if (cached) {
      return cached
    }
    const rawList = this._memBuckets.get(relPath) ?? []
    const qs: Question[] = []
    for (const raw of rawList) {
      const q = toQuestion(raw)
      if (q !== null) {
        qs.push(q)
      }
    }
    this._bucketCache.set(relPath, qs)
    for (const q of qs) {
      this._byId.set(q.id, q)
    }
    return qs
  }

  questionsInGroup(name: string): Question[] {
    const cached = this._groupCache.get(name)
    if (cached) {
      return cached
    }
    const group = this.group(name)
    const qs: Question[] = []
    if (group) {
      for (const f of group.files) {
        qs.push(...this.loadBucket(f.path))
      }
    }
    this._groupCache.set(name, qs)
    return qs
  }

  get(questionId: string): Question | null {
    const hit = this._byId.get(questionId)
    if (hit) {
      return hit
    }
    for (const g of this.groups()) {
      this.questionsInGroup(g.name)
      const found = this._byId.get(questionId)
      if (found) {
        return found
      }
    }
    return null
  }

  /** 全量加载所有组题目（统计用，注意会触发全部桶构建）。 */
  activeQuestions(): Question[] {
    const qs: Question[] = []
    for (const g of this.groups()) {
      qs.push(...this.questionsInGroup(g.name))
    }
    return qs
  }
}

/** 全量校验后加载的正式题库单例（引擎各模块共用）。 */
export const bank: BucketBank = BucketBank.load()
