<script setup lang="ts">
/**
 * ResultView — 结果页
 * --------------------------------------------------------------------------
 * 顶部：概览三卡（进度 / 置信度 / 矛盾数）
 * 中部：10 维度按分数降序排列
 * 底部：矛盾分析 + 不确定维度提示
 * （结果内容渲染复用 ResultContent 组件）
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTestStore } from '@/stores/test'
import { useSessionRestore } from '@/composables/useSessionRestore'
import { useShareResult } from '@/composables/useShareResult'
import ResultContent from '@/components/ResultContent.vue'
import LoadingState from '@/components/LoadingState.vue'

const router = useRouter()
const store = useTestStore()
const { clear, loadCachedResult } = useSessionRestore()
const { phase, isMobile, share } = useShareResult()

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

/** 分享按钮文案随流程状态变化 */
const shareLabel = computed(() => {
  switch (phase.value) {
    case 'generating':
      return '生成中…'
    case 'ready':
      return '已生成 ✓'
    case 'error':
      return '重试'
    default:
      return '分享结果'
  }
})

function startOver() {
  clear()
  store.reset()
  router.push({ name: 'intro' })
}

/** 浏览器端生成结果卡片 PNG，引导保存/分享 */
async function shareResult() {
  if (!store.result || phase.value === 'generating') return
  await share(store.result)
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
    <!-- ============================== 结果内容 ============================== -->
    <ResultContent :result="store.result" />

    <!-- ============================== 行动 ============================== -->
    <div class="mt-12 flex flex-col sm:flex-row gap-3 sm:gap-4">
      <button
        type="button"
        class="btn-primary flex-1"
        :disabled="phase === 'generating'"
        @click="shareResult"
      >
        {{ shareLabel }}
      </button>
      <button type="button" class="btn-ghost flex-1" @click="copyLink">
        <span v-if="!showShareHint">复制链接</span>
        <span v-else>已复制 ✓</span>
      </button>
      <button type="button" class="btn-ghost flex-1" @click="startOver">
        再测一次
      </button>
    </div>

    <!-- 分享流程反馈（短暂提示） -->
    <p
      v-if="phase === 'ready'"
      class="mt-4 text-center text-sm text-emerald-600 dark:text-emerald-400"
      role="status"
    >
      {{
        isMobile
          ? '图片已生成，请在分享面板中选择「存储图像」或发送到任意应用。'
          : '图片已下载，可分享到任意平台。'
      }}
    </p>
    <p
      v-if="phase === 'error'"
      class="mt-4 text-center text-sm text-red-500 dark:text-red-400"
      role="alert"
    >
      图片生成失败，请重试。
    </p>

    <p
      class="mt-8 text-center text-xs text-ink-500 dark:text-ink-400 leading-relaxed"
    >
      这份结果不是你的"人格标签"。<br />
      允许自己在不同情境下呈现不同倾向，这就是真实的人。
    </p>
    <p class="mt-2 text-center text-xs text-ink-400 dark:text-ink-500">
      分享卡片在浏览器本地生成，不含题目与原始回答，仅展示倾向与分值。
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
