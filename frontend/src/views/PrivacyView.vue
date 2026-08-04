<script setup lang="ts">
/**
 * PrivacyView — 隐私政策页
 * ============================================================================
 * 从后端 GET /api/meta/privacy 拉取政策正文（保留期等参数由后端按实际配置填充）；
 * 后端不可用（如纯静态托管 / 离线）时回退到本文件内置文案。
 *
 * ⚠️ 双源同步：本文件 FALLBACK_PRIVACY 需与 backend/app/routers/meta.py 的
 *    privacy 接口内容保持一致；改一处时务必同步另一处。
 * ============================================================================
 */
import { onMounted, ref } from 'vue'
import { testApi } from '@/api/client'
import type { PrivacyResponse } from '@/types/api'

/** 后端不可用时的回退文案（与 backend/app/routers/meta.py 同步）。 */
const FALLBACK_PRIVACY: PrivacyResponse = {
  version: '1.0',
  effective_date: '2026-08-04',
  retention: { session_ttl_days: 3, completed_session_ttl_days: 15 },
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
        '使用测试功能时，服务端会保存：\n' +
        '- 你对每道题的答案（是/否）与作答耗时；\n' +
        '- 答案的修改记录（修改前/后的答案）；\n' +
        '- 测试结果（10 个价值维度的分数、一致性、置信度）；\n' +
        '- 随机会话标识（仅用于把同一测试的数据关联起来）。',
    },
    {
      title: '我们不收集什么',
      body:
        '我们不收集姓名、邮箱、手机号等个人身份信息；' +
        '不使用 Cookie 进行追踪；不投放广告。',
    },
    {
      title: '服务端数据保留',
      body:
        '服务端数据保存在 SQLite 数据库中，并按期自动删除：\n' +
        '- 进行中的测试会话默认保留 3 天；\n' +
        '- 已完成的测试结果默认保留 15 天。\n' +
        '到期后，相关答案、结果与修改记录会被后台任务一并删除。',
    },
    {
      title: '数据用途',
      body:
        '收集的数据仅用于：生成本次测试结果，以及以匿名统计形式改进' +
        '测试质量（如题目区分度、完成率）。我们不会用这些数据识别你的' +
        '个人身份。',
    },
    {
      title: '数据共享',
      body: '我们不会向任何第三方出售、出租或共享你的测试数据。',
    },
    {
      title: '客户端本地存储',
      body:
        '结果存档保存在你的浏览器本地存储（localStorage）中，最多保留' +
        ' 50 条，仅存本机、不上传服务器；答题进度临时保存在会话存储' +
        '（sessionStorage）中，24 小时后或关闭标签页后自动清除。',
    },
    {
      title: '限流与安全',
      body:
        '为防滥用，服务端会基于 IP 做请求频率限制；该信息仅存于内存，' +
        '不持久化，也不用于识别身份。',
    },
    {
      title: '你的权利',
      body:
        '你可以随时在首页删除本地存档。服务端数据到期后会自动删除，' +
        '无需额外操作。',
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

const privacy = ref<PrivacyResponse>(FALLBACK_PRIVACY)
const loadError = ref(false)

onMounted(async () => {
  try {
    privacy.value = await testApi.getPrivacy()
  } catch (e) {
    loadError.value = true
    console.warn('[PrivacyView] 拉取隐私政策失败，使用内置回退文案：', e)
  }
})
</script>

<template>
  <section class="mx-auto max-w-3xl px-6 py-12 sm:py-16">
    <!-- ============================== 头部 ============================== -->
    <div class="mb-8 animate-slide-up">
      <p
        class="text-xs uppercase tracking-[0.3em] text-ink-500 dark:text-ink-400 mb-4"
      >
        Privacy Policy
      </p>
      <h1
        class="font-serif text-3xl sm:text-4xl font-semibold text-ink-900 dark:text-ink-50 mb-3"
      >
        隐私政策
      </h1>
      <p class="text-sm text-ink-500 dark:text-ink-400">
        版本 {{ privacy.version }} · 生效日期 {{ privacy.effective_date }}
      </p>
    </div>

    <!-- ============================== 正文 ============================== -->
    <div class="space-y-4 animate-fade-in">
      <div
        v-for="s in privacy.sections"
        :key="s.title"
        class="card p-5 sm:p-6"
      >
        <h2
          class="font-serif text-lg font-semibold text-ink-900 dark:text-ink-100 mb-2"
        >
          {{ s.title }}
        </h2>
        <p
          class="text-[14px] leading-relaxed text-ink-700 dark:text-ink-300 whitespace-pre-line"
        >
          {{ s.body }}
        </p>
      </div>
    </div>

    <p v-if="loadError" class="mt-4 text-xs text-ink-400 dark:text-ink-500">
      提示：未能从服务器获取最新政策，当前显示内置版本。
    </p>
  </section>
</template>
