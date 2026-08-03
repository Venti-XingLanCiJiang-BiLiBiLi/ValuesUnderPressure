<script setup lang="ts">
/**
 * ResultView — 结果页
 * --------------------------------------------------------------------------
 * 顶部：概览三卡（进度 / 置信度 / 矛盾数）
 * 中部：10 维度按分数降序排列
 * 底部：矛盾分析 + 不确定维度提示
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTestStore } from '@/stores/test'
import { useSessionRestore } from '@/composables/useSessionRestore'
import { BRAND } from '@/config/branding'
import DimensionBar from '@/components/DimensionBar.vue'
import ConflictCard from '@/components/ConflictCard.vue'
import LoadingState from '@/components/LoadingState.vue'

const router = useRouter()
const store = useTestStore()
const { clear, loadCachedResult } = useSessionRestore()

onMounted(async () => {
  // 已有结果，直接展示
  if (store.sessionId && store.result) return

  // 尝试从 sessionStorage 恢复缓存结果（App.vue 可能已处理，这里做兜底）
  const cached = loadCachedResult()
  if (cached) {
    store.restoreFromCache(cached.sessionId, cached.result)
    return
  }

  // 有 sessionId 但无结果 → 尝试从后端拉取（可能仍在后端存储中）
  if (store.sessionId && !store.result) {
    await store.fetchResult()
    if (store.result) return
  }

  // 无法恢复 → 回到首页
  router.replace({ name: 'intro' })
})

const showShareHint = ref(false)
const confidencePercent = computed(() => Math.round((store.result?.confidence ?? 0) * 100))

function startOver() {
  clear()
  store.reset()
  router.push({ name: 'intro' })
}

async function copyLink() {
  try {
    // 复制"应用首页"链接（含仓库子路径），部署在 GitHub Pages 子路径下也正确
    await navigator.clipboard.writeText(
      window.location.origin + window.location.pathname,
    )
    showShareHint.value = true
    setTimeout(() => (showShareHint.value = false), 2000)
  } catch {
    // ignore
  }
}
</script>

<template>
  <section v-if="store.result" class="mx-auto max-w-3xl px-6 py-10 sm:py-16">
    <!-- ============================== Header ============================== -->
    <div class="text-center mb-10 animate-fade-in">
      <p class="text-xs uppercase tracking-[0.3em] text-ember-600 dark:text-ember-400 mb-3">
        你的价值画像
      </p>
      <h1
        class="font-serif text-3xl sm:text-4xl font-semibold text-ink-900 dark:text-ink-50 mb-4"
      >
        {{ BRAND.name }}
      </h1>
      <p
        class="text-ink-600 dark:text-ink-300 text-base max-w-md mx-auto"
      >
        以下是
        <strong class="text-ink-900 dark:text-ink-100">{{ store.result.answered_count }}</strong>
        道题中你的倾向分布。
        结果只描述倾向，不做人格定性。
      </p>
    </div>

    <!-- ============================== 概览 ============================== -->
    <div class="grid sm:grid-cols-3 gap-3 mb-8">
      <div class="card p-4 text-center">
        <p class="text-xs text-ink-500 dark:text-ink-400 mb-1">作答进度</p>
        <p class="font-mono text-2xl text-ink-900 dark:text-ink-100 tabular-nums">
          {{ store.result.answered_count }} / {{ store.result.total }}
        </p>
      </div>
      <div class="card p-4 text-center">
        <p class="text-xs text-ink-500 dark:text-ink-400 mb-1">整体置信度</p>
        <p class="font-mono text-2xl text-ink-900 dark:text-ink-100 tabular-nums">
          {{ confidencePercent }}%
        </p>
      </div>
      <div class="card p-4 text-center">
        <p class="text-xs text-ink-500 dark:text-ink-400 mb-1">矛盾组合</p>
        <p class="font-mono text-2xl text-ink-900 dark:text-ink-100 tabular-nums">
          {{ store.result.conflicts.length }}
        </p>
      </div>
    </div>

    <!-- ============================== 维度列表 ============================== -->
    <h2 class="font-serif text-2xl font-semibold text-ink-900 dark:text-ink-100 mb-4 mt-10">
      10 个价值维度
    </h2>
    <div class="space-y-3 mb-10">
      <DimensionBar
        v-for="(dim, idx) in store.sortedDimensions"
        :key="dim.dimension"
        :dim="dim"
        :rank="idx + 1"
      />
    </div>

    <!-- ============================== 矛盾分析 ============================== -->
    <div v-if="store.result.conflicts.length > 0" class="mt-12">
      <h2 class="font-serif text-2xl font-semibold text-ink-900 dark:text-ink-100 mb-2">
        矛盾分析
      </h2>
      <p class="text-sm text-ink-600 dark:text-ink-300 mb-5 leading-relaxed">
        你的回答在以下维度组合上同时表现强烈——这不是错误，恰恰是真实的你。
        价值之间的张力，本身就是人之为人的复杂度。
      </p>
      <div class="space-y-3">
        <ConflictCard
          v-for="(c, i) in store.result.conflicts"
          :key="i"
          :conflict="c"
        />
      </div>
    </div>

    <!-- ============================== 不确定维度 ============================== -->
    <div
      v-if="store.result.uncertain_dimensions.length > 0"
      class="mt-10 rounded-2xl border border-ink-200 bg-ink-50 p-5
             dark:border-ink-700 dark:bg-ink-900/60"
    >
      <h3 class="font-serif text-base font-semibold text-ink-900 dark:text-ink-100 mb-2">
        作答一致性偏低的维度
      </h3>
      <p class="text-sm text-ink-600 dark:text-ink-300 leading-relaxed">
        以下维度在不同题目间的作答方向不一致，可能受具体情境影响较大：
        <span class="text-ink-900 dark:text-ink-100 font-medium ml-1">
          {{ store.result.uncertain_dimensions.join('、') }}
        </span>
      </p>
    </div>

    <!-- ============================== 行动 ============================== -->
    <div class="mt-12 flex flex-col sm:flex-row gap-3 sm:gap-4">
      <button type="button" class="btn-primary flex-1" @click="startOver">
        再测一次
      </button>
      <button type="button" class="btn-ghost flex-1" @click="copyLink">
        <span v-if="!showShareHint">复制链接</span>
        <span v-else>已复制 ✓</span>
      </button>
    </div>

    <p
      class="mt-8 text-center text-xs text-ink-500 dark:text-ink-400 leading-relaxed"
    >
      这份结果不是你的"人格标签"。<br />
      允许自己在不同情境下呈现不同倾向，这就是真实的人。
    </p>
  </section>

  <section v-else class="mx-auto max-w-3xl px-6 py-20">
    <LoadingState v-if="store.loading" label="正在生成你的价值画像…" />
    <div v-else class="text-center">
      <p class="text-ink-500 dark:text-ink-400">还没有测试结果</p>
      <button class="btn-primary mt-4" @click="router.push({ name: 'intro' })">
        开始测试
      </button>
    </div>
  </section>
</template>
