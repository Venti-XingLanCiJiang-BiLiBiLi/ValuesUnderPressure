<script setup lang="ts">
/**
 * ArchiveView — 存档查看页
 * --------------------------------------------------------------------------
 * 两种模式：
 * - 本地存档：route.params.sessionId → localStorage（useArchives）；
 * - 云端存档（Toy）：route.query.cloud = 时间戳 → 云存储完整结果分块重组。
 * 支持返回首页、删除该条存档与生成分享图片（复用 ShareResultModal）。
 * 数据完全来自本地 / 云存储，无需后端。
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useArchives } from '@/composables/useArchives'
import { useToyCloudArchive } from '@/composables/useToyCloudArchive'
import ResultContent from '@/components/ResultContent.vue'
import ShareResultModal from '@/components/ShareResultModal.vue'
import type { ResultResponse } from '@/types/api'

const route = useRoute()
const router = useRouter()
const { getArchive, deleteArchive } = useArchives()
const { getCloudResult, deleteCloudArchive } = useToyCloudArchive()

const sessionId = computed(() => String(route.params.sessionId))
const archive = computed(() => getArchive(sessionId.value))

/** 云端模式时间戳；非云端模式为 null。 */
const cloudTs = computed(() => {
  const q = route.query.cloud
  if (!q) return null
  const n = Number(q)
  return Number.isFinite(n) && n > 0 ? n : null
})
const isCloud = computed(() => cloudTs.value !== null)

const cloudResult = ref<ResultResponse | null>(null)
const cloudLoading = ref(false)
const cloudFailed = ref(false)

watch(
  cloudTs,
  async (ts) => {
    if (ts === null) return
    cloudLoading.value = true
    cloudFailed.value = false
    cloudResult.value = null
    cloudResult.value = await getCloudResult(ts)
    cloudLoading.value = false
    if (!cloudResult.value) cloudFailed.value = true
  },
  { immediate: true },
)

const showShare = ref(false)

/** 当前展示的结果：云端完整结果优先，其次本地存档。 */
const result = computed<ResultResponse | null>(() => cloudResult.value ?? archive.value?.result ?? null)

const displayTime = computed(() =>
  isCloud.value ? cloudTs.value! : (archive.value?.savedAt ?? 0),
)

const formattedDate = computed(() => {
  const t = displayTime.value
  if (!t) return ''
  const d = new Date(t)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
})

function goBack() {
  router.push({ name: 'intro' })
}

async function remove() {
  if (isCloud.value) {
    const ts = cloudTs.value!
    if (await deleteCloudArchive(ts)) {
      router.push({ name: 'intro' })
    }
    return
  }
  if (!archive.value) return
  deleteArchive(sessionId.value)
  router.push({ name: 'intro' })
}
</script>

<template>
  <!-- 云端加载中 -->
  <section
    v-if="cloudLoading"
    class="mx-auto max-w-3xl px-6 py-20 flex flex-col items-center gap-3"
    role="status"
  >
    <span
      class="inline-block h-8 w-8 animate-spin rounded-full border-2 border-ink-200 border-t-ember-500"
    />
    <p class="text-sm text-ink-500 dark:text-ink-400">正在加载云端存档…</p>
  </section>

  <section v-else-if="result" class="mx-auto max-w-3xl px-6 py-10 sm:py-16">
    <!-- ============================== 存档头部 ============================== -->
    <div class="flex items-center justify-between gap-3 mb-6 animate-fade-in">
      <button type="button" class="btn-ghost shrink-0" @click="goBack">← 返回</button>
      <span
        class="text-xs text-ink-500 dark:text-ink-400 font-mono tabular-nums truncate"
        :title="`存档时间：${formattedDate}`"
      >
        {{ isCloud ? '☁️' : '📁' }} {{ formattedDate }}
      </span>
      <button
        type="button"
        class="btn-ghost shrink-0 text-red-600 hover:bg-red-50
               dark:text-red-400 dark:hover:bg-red-950/40"
        @click="remove"
      >
        删除存档
      </button>
    </div>

    <!-- ============================== 存档内容 ============================== -->
    <ResultContent :result="result" />

    <div class="mt-12 flex flex-col sm:flex-row gap-3 sm:gap-4">
      <button type="button" class="btn-primary flex-1" @click="showShare = true">
        分享结果
      </button>
      <button type="button" class="btn-ghost flex-1" @click="goBack">
        返回首页
      </button>
    </div>
  </section>

  <section v-else-if="cloudFailed" class="mx-auto max-w-3xl px-6 py-20">
    <div class="text-center animate-fade-in">
      <div class="text-4xl mb-3">☁️</div>
      <p class="text-ink-500 dark:text-ink-400 mb-2">
        云端存档读取失败或数据不完整
      </p>
      <p class="text-xs text-ink-400 dark:text-ink-500 mb-6">
        可能未登录 B 站、存储被清理或仅剩摘要数据，请返回重新查看。
      </p>
      <button type="button" class="btn-primary" @click="goBack">返回首页</button>
    </div>
  </section>

  <section v-else class="mx-auto max-w-3xl px-6 py-20">
    <div class="text-center animate-fade-in">
      <div class="text-4xl mb-3">🗂️</div>
      <p class="text-ink-500 dark:text-ink-400 mb-2">
        存档不存在或已被删除
      </p>
      <p class="text-xs text-ink-400 dark:text-ink-500 mb-6">
        完成一次测试后，结果会自动保存为本地存档。
      </p>
      <button type="button" class="btn-primary" @click="goBack">返回首页</button>
    </div>
  </section>

  <!-- 分享预览弹窗（结果页与存档页共用的唯一分享实现） -->
  <ShareResultModal v-model:show="showShare" :result="result" />
</template>
