<script setup lang="ts">
/**
 * ResultView — 结果页
 * --------------------------------------------------------------------------
 * 顶部：概览三卡（进度 / 置信度 / 矛盾数）
 * 中部：10 维度按分数降序排列
 * 底部：矛盾分析 + 不确定维度提示
 * 分享：打开 ShareResultModal → 预览生成图片 →「下载结果」（与存档页共用组件）
 * （结果内容渲染复用 ResultContent 组件）
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTestStore } from '@/stores/test'
import { useSessionRestore } from '@/composables/useSessionRestore'
import ResultContent from '@/components/ResultContent.vue'
import ShareResultModal from '@/components/ShareResultModal.vue'
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

const showShare = ref(false)
const showShareHint = ref(false)

function startOver() {
  clear()
  store.reset()
  router.push({ name: 'intro' })
}

/** 打开分享预览弹窗（图片在弹窗内生成）。 */
function shareResult() {
  if (!store.result) return
  showShare.value = true
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
      <button type="button" class="btn-primary flex-1" @click="shareResult">
        分享结果
      </button>
      <button type="button" class="btn-ghost flex-1" @click="copyLink">
        <span v-if="!showShareHint">复制链接</span>
        <span v-else>已复制 ✓</span>
      </button>
      <button type="button" class="btn-ghost flex-1" @click="startOver">
        再测一次
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

  <!-- 分享预览弹窗（结果页与存档页共用的唯一分享实现） -->
  <ShareResultModal v-model:show="showShare" :result="store.result" />
</template>
