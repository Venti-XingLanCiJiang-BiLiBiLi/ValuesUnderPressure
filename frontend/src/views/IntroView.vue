<script setup lang="ts">
/**
 * IntroView — 开屏介绍页
 * --------------------------------------------------------------------------
 * 选择题量 (20/40/60) → 创建会话 → 跳转 /test
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTestStore } from '@/stores/test'
import { BRAND } from '@/config/branding'

const router = useRouter()
const store = useTestStore()

const questionCount = ref(40)
const starting = ref(false)
const localError = ref<string | null>(null)

async function handleStart() {
  starting.value = true
  localError.value = null
  await store.startSession(questionCount.value)
  starting.value = false

  if (store.error) {
    localError.value = store.error
    return
  }
  router.push({ name: 'test' })
}
</script>

<template>
  <section class="mx-auto max-w-3xl px-6 py-12 sm:py-20">
    <!-- ============================== Hero ============================== -->
    <div class="text-center mb-12 animate-slide-up">
      <p class="text-xs uppercase tracking-[0.3em] text-ink-500 dark:text-ink-400 mb-4">
        {{ BRAND.nameEn }}
      </p>
      <h1
        class="font-serif text-4xl sm:text-5xl font-semibold text-ink-900 dark:text-ink-50 mb-6 leading-tight"
      >
        {{ BRAND.name }}
      </h1>
      <p
        class="text-ink-600 dark:text-ink-300 text-lg sm:text-xl max-w-xl mx-auto leading-relaxed"
      >
        不是人格分类，只描述倾向。<br class="sm:hidden" />
        直面极端价值冲突，看清你的底线与优先级。
      </p>
    </div>

    <!-- ============================== 介绍卡 ============================== -->
    <div class="card p-6 sm:p-8 mb-6 animate-fade-in">
      <h2 class="font-serif text-xl font-semibold text-ink-900 dark:text-ink-100 mb-4">
        这不是一份"性格测试"
      </h2>
      <div class="space-y-3 text-ink-700 dark:text-ink-300 leading-relaxed text-[15px]">
        <p>
          你将面对一系列
          <strong class="text-ink-900 dark:text-ink-100">极端情境下的两难问题</strong>。
          没有"正确答案"，只有你的取舍。
        </p>
        <p>
          测试会从
          <strong class="text-ink-900 dark:text-ink-100">10 个价值维度</strong>
          描述你的倾向—— 自由、安全、隐私、利他、规则、长期……
        </p>
        <p>
          我们<strong class="text-ink-900 dark:text-ink-100">不会</strong>
          给你贴上"INFP"或"完美主义"这样的标签。
          你的答案允许矛盾、允许随情境变化——这本身就被记录下来。
        </p>
      </div>
    </div>

    <!-- ============================== 流程说明 ============================== -->
    <div class="grid sm:grid-cols-3 gap-3 mb-8">
      <div class="card p-4 text-center">
        <div class="text-2xl mb-1">⚖️</div>
        <p class="text-sm font-medium text-ink-800 dark:text-ink-200">逐题 Y/N</p>
        <p class="text-xs text-ink-500 dark:text-ink-400 mt-1">约 5-8 分钟</p>
      </div>
      <div class="card p-4 text-center">
        <div class="text-2xl mb-1">📊</div>
        <p class="text-sm font-medium text-ink-800 dark:text-ink-200">10 维度评分</p>
        <p class="text-xs text-ink-500 dark:text-ink-400 mt-1">含一致性</p>
      </div>
      <div class="card p-4 text-center">
        <div class="text-2xl mb-1">🔍</div>
        <p class="text-sm font-medium text-ink-800 dark:text-ink-200">矛盾分析</p>
        <p class="text-xs text-ink-500 dark:text-ink-400 mt-1">情境依赖提示</p>
      </div>
    </div>

    <!-- ============================== 设置 & 开始 ============================== -->
    <div class="card p-6 sm:p-8">
      <label class="block text-sm font-medium text-ink-800 dark:text-ink-200 mb-3">
        题目数量
      </label>
      <div class="grid grid-cols-3 gap-2 mb-6">
        <button
          v-for="n in [20, 40, 60]"
          :key="n"
          type="button"
          class="rounded-xl py-3 text-sm font-medium transition-all ring-1"
          :class="
            questionCount === n
              ? 'bg-ink-900 text-white ring-ink-900 dark:bg-ink-100 dark:text-ink-900 dark:ring-ink-100'
              : 'bg-white text-ink-700 ring-ink-200 hover:ring-ink-400 dark:bg-ink-800 dark:text-ink-200 dark:ring-ink-700 dark:hover:ring-ink-500'
          "
          @click="questionCount = n"
        >
          {{ n }} 题
          <span class="block text-xs mt-0.5 opacity-70">
            {{ n === 20 ? '快速' : n === 40 ? '推荐' : '深入' }}
          </span>
        </button>
      </div>

      <button
        type="button"
        class="btn-primary w-full text-base"
        :disabled="starting"
        @click="handleStart"
      >
        <span v-if="!starting">开始测试</span>
        <span v-else class="inline-flex items-center gap-2">
          <span
            class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white dark:border-ink-900/30 dark:border-t-ink-900"
          />
          准备中…
        </span>
      </button>

      <p
        v-if="localError"
        class="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200
               dark:bg-red-950/40 dark:text-red-300 dark:ring-red-900/50"
      >
        {{ localError }}
        <br />
        <span class="text-xs text-red-600 dark:text-red-400">
          请确认后端服务已启动（默认 http://127.0.0.1:8000）。
        </span>
      </p>
    </div>

    <p class="mt-8 text-center text-xs text-ink-500 dark:text-ink-400">
      本测试不需要登录，答案仅用于生成你的结果。
    </p>
  </section>
</template>
