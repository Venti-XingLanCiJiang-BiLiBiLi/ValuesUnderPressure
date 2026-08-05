<script setup lang="ts">
/**
 * ArchiveView — 存档查看页
 * --------------------------------------------------------------------------
 * 从 localStorage 读取指定 sessionId 的存档结果并展示，
 * 支持返回首页、删除该条存档与生成分享图片（复用 ShareResultModal）。
 * 数据完全来自本地，无需后端。
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useArchives } from '@/composables/useArchives'
import ResultContent from '@/components/ResultContent.vue'
import ShareResultModal from '@/components/ShareResultModal.vue'

const route = useRoute()
const router = useRouter()
const { getArchive, deleteArchive } = useArchives()

const sessionId = computed(() => String(route.params.sessionId))
const archive = computed(() => getArchive(sessionId.value))

const showShare = ref(false)

const formattedDate = computed(() => {
  const t = archive.value?.savedAt
  if (!t) return ''
  const d = new Date(t)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
})

function goBack() {
  router.push({ name: 'intro' })
}

function remove() {
  if (!archive.value) return
  deleteArchive(sessionId.value)
  router.push({ name: 'intro' })
}
</script>

<template>
  <section v-if="archive" class="mx-auto max-w-3xl px-6 py-10 sm:py-16">
    <!-- ============================== 存档头部 ============================== -->
    <div class="flex items-center justify-between gap-3 mb-6 animate-fade-in">
      <button type="button" class="btn-ghost shrink-0" @click="goBack">← 返回</button>
      <span
        class="text-xs text-ink-500 dark:text-ink-400 font-mono tabular-nums truncate"
        :title="`存档时间：${formattedDate}`"
      >
        📁 {{ formattedDate }}
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
    <ResultContent :result="archive.result" />

    <div class="mt-12 flex flex-col sm:flex-row gap-3 sm:gap-4">
      <button type="button" class="btn-primary flex-1" @click="showShare = true">
        分享结果
      </button>
      <button type="button" class="btn-ghost flex-1" @click="goBack">
        返回首页
      </button>
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
  <ShareResultModal v-model:show="showShare" :result="archive?.result ?? null" />
</template>
