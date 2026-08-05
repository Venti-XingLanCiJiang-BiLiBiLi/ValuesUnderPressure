<script setup lang="ts">
/**
 * PrivacyView — 隐私政策页
 * ============================================================================
 * Toy 静态托管无后端，政策文案静态打包在本地引擎（LOCAL_PRIVACY）中，
 * 页面直接展示，无网络请求。
 * ============================================================================
 */
import { LOCAL_PRIVACY } from '@/engine'
import type { PrivacyResponse } from '@/types/api'

const privacy: PrivacyResponse = LOCAL_PRIVACY
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
  </section>
</template>
