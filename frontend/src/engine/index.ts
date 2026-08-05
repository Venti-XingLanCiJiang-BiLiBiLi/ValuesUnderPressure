/**
 * 本地引擎 API 门面（localTestApi）。
 *
 * 方法签名对齐 frontend/src/api/client.ts 的 testApi，便于后续阶段
 * 无痛替换（切换入口即可，调用方不用改）：
 *   - health / getDimensions / getPrivacy / createSession /
 *     nextQuestion / submitAnswer / getResult，全部 async。
 *
 * 隐私政策为静态文案（本地引擎无服务端保留期语义，保留后端结构以便
 * 前端 PrivacyView 直接消费）。
 */

import { bank, DIMENSION_IDS } from './bank'
import { DIMENSIONS } from './scoring'
import {
  createLocalStorageSessionStore,
  createSessionManager,
  type SessionManager,
} from './session'
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
} from '../types/api'

/** 本地会话管理器单例（localStorage 持久化）。 */
export const sessionManager: SessionManager = createSessionManager({
  storage: createLocalStorageSessionStore(),
})

/** 静态隐私政策文案（对齐后端 routers/meta.py，本地引擎无服务端数据保留）。 */
export const LOCAL_PRIVACY: PrivacyResponse = {
  version: '1.0',
  effective_date: '2026-08-04',
  retention: {
    session_ttl_days: 3,
    completed_session_ttl_days: 15,
  },
  sections: [
    {
      title: '概述',
      body:
        '本应用（取舍之间 · Values Under Pressure）致力于最小化数据收集。' +
        '你无需注册或登录即可使用测试功能。',
    },
    {
      title: '我们收集什么',
      body:
        '使用测试功能时，本应用会在你的浏览器本地保存：\n' +
        '- 你对每道题的答案（是/否）与作答耗时；\n' +
        '- 答案的修改记录（修改前/后的答案）；\n' +
        '- 测试结果（10 个价值维度的分数、一致性、置信度）；\n' +
        '- 随机会话标识（仅用于把同一测试的数据关联起来）。\n' +
        '在 B 站 Toy 环境登录使用时，完成测试后会把「结果摘要」' +
        '（各维度分数、置信度、作答数、时间）备份到 B 站云存储，' +
        '按你的 B 站账号隔离，用于跨设备查看存档。',
    },
    {
      title: '我们不收集什么',
      body:
        '我们不收集姓名、邮箱、手机号等个人身份信息；' +
        '不使用 Cookie 进行追踪；不投放广告；题目与原始回答仅存本机，' +
        '不会上传。',
    },
    {
      title: '数据保留',
      body:
        '本地数据保存在你的浏览器本地存储（localStorage / sessionStorage），' +
        '由浏览器管理生命周期，可随时清除。云端存档保存在 B 站 Toy 云存储' +
        '（按登录用户隔离），单个 Toy 最多 128 条，可在首页「云端存档」中' +
        '手动删除。',
    },
    {
      title: '数据用途',
      body:
        '收集的数据仅用于：生成本次测试结果，以及跨设备回顾你的存档。' +
        '我们不会用这些数据识别你的个人身份。',
    },
    {
      title: '数据共享',
      body:
        '我们不会向任何第三方出售、出租或共享你的测试数据；云端存档由' +
        'B 站（哔哩哔哩）作为存储服务方按其隐私政策处理。',
    },
    {
      title: '你的权利',
      body:
        '你可以随时在首页删除本地存档，或清除浏览器站点数据。',
    },
    {
      title: '政策变更与联系方式',
      body:
        '本政策如发生变更，我们会更新版本号与生效日期。如有疑问或需要' +
        '删除数据，可通过项目仓库联系：' +
        'https://github.com/Venti-XingLanCiJiang-BiLiBiLi/ValuesUnderPressure',
    },
  ],
}

/** 本地引擎测试 API（签名对齐 frontend/src/api/client.ts 的 testApi）。 */
export const localTestApi = {
  async health(): Promise<HealthResponse> {
    return {
      status: 'ok',
      question_bank_version: bank.version(),
      groups: bank.groups().length,
      active_questions: bank.totalQuestions(),
    }
  },

  async getDimensions(): Promise<Record<string, DimensionMeta>> {
    const payload: Record<string, DimensionMeta> = {}
    for (const [dim, meta] of Object.entries(DIMENSIONS)) {
      payload[dim] = {
        name: meta.name,
        description: meta.description,
        direction: meta.direction,
      }
    }
    return payload
  },

  async getPrivacy(): Promise<PrivacyResponse> {
    return LOCAL_PRIVACY
  },

  async createSession(
    req: CreateSessionRequest = {},
  ): Promise<CreateSessionResponse> {
    return sessionManager.createSession(req)
  },

  async nextQuestion(sessionId: string): Promise<QuestionResponse> {
    return sessionManager.nextQuestion(sessionId)
  },

  async submitAnswer(
    sessionId: string,
    req: SubmitAnswerRequest,
  ): Promise<SubmitAnswerResponse> {
    return sessionManager.submitAnswer(sessionId, req)
  },

  async getResult(sessionId: string): Promise<ResultResponse> {
    return sessionManager.getResult(sessionId)
  },
}

// 便于调试/测试：暴露引擎内部维度列表与题目总数。
export { DIMENSION_IDS, bank }
