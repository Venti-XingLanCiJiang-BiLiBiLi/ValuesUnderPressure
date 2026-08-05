<script setup lang="ts">
/**
 * ShareResultModal — 结果分享弹窗（结果页 / 存档页共用）
 * ============================================================================
 * 流程：打开弹窗 → 浏览器端生成结果卡片（renderShareCard，本地完成、
 * 不上传任何数据）→ 页面内展示图片预览 → 保存。
 *
 * 保存方式（按环境自动选择）：
 * 0) B站 App（Toy 环境）→ 主按钮「保存到相册」（toy.saveImageToAlbum，
 *    base64 超限自动 JPEG 压缩/降尺寸），另有「下载结果」；
 * 1) 普通浏览器 → 主按钮「下载结果」（长按图片也可保存到相册）。
 *
 * 复用 utils/shareCard.ts 的既有图片生成逻辑；本组件是唯一的分享入口，
 * 结果页与存档页直接引用，不复制代码。
 * ============================================================================
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { ResultResponse } from '@/types/api'
import { getToy } from '@/composables/useToy'
import { renderShareCard, canvasToBlob, downloadBlob } from '@/utils/shareCard'
import { useDimensionMeta } from '@/composables/useDimensionMeta'

// 维度元数据（题库 dimensions.json）：供卡片条底两端高低分标签使用
const { meta, load } = useDimensionMeta()

const props = defineProps<{
  show: boolean
  result: ResultResponse | null
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
}>()

/** saveImageToAlbum 的 base64 上限为 2M，预留 10% 余量。 */
const MAX_ALBUM_BASE64 = 1.8 * 1024 * 1024

const generating = ref(false)
const failed = ref(false)
const blob = ref<Blob | null>(null)
const previewUrl = ref<string | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const albumSupported = ref(false)
const albumSaving = ref(false)
const albumSaved = ref(false)

const primaryLabel = computed(() => {
  if (albumSupported.value) return '保存到相册'
  return '下载结果'
})

function close() {
  emit('update:show', false)
}

/** 生成结果卡片预览（进入弹窗时自动触发；失败可点击重试）。 */
async function generate() {
  if (!props.result) return
  generating.value = true
  failed.value = false
  albumSaved.value = false
  try {
    // 拉取维度元数据（幂等，已缓存则直接复用），供卡片条底两端高低分标签使用
    await load()
    const nextCanvas = renderShareCard(props.result, { meta: meta.value })
    const nextBlob = await canvasToBlob(nextCanvas)
    if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
    canvas.value = nextCanvas
    blob.value = nextBlob
    previewUrl.value = URL.createObjectURL(nextBlob)
  } catch {
    failed.value = true
  } finally {
    generating.value = false
  }
}

function download() {
  if (!blob.value) return
  downloadBlob(blob.value)
}

/**
 * B站 App 内保存结果卡片到系统相册。
 * base64 超过 SDK 上限（2M）时自动降级：先 JPEG 压缩，仍超则用 1x 尺寸重渲染。
 */
async function saveToAlbum() {
  const toy = getToy()
  if (!toy || !props.result || !canvas.value) return
  albumSaving.value = true
  try {
    let dataUrl = canvas.value.toDataURL('image/png')
    if (dataUrl.length > MAX_ALBUM_BASE64) {
      dataUrl = canvas.value.toDataURL('image/jpeg', 0.9)
    }
    if (dataUrl.length > MAX_ALBUM_BASE64) {
      dataUrl = renderShareCard(props.result, {
        scale: 1,
        meta: meta.value,
      }).toDataURL('image/jpeg', 0.85)
    }
    // SDK 字段为裸 base64 数据（不含 data:...;base64, 前缀）
    const base64Data = dataUrl.slice(dataUrl.indexOf(',') + 1)
    await toy.saveImageToAlbum({
      base64Data,
      hintMsg: '需要相册权限来保存你的结果卡片',
    })
    albumSaved.value = true
  } catch {
    failed.value = true
  } finally {
    albumSaving.value = false
  }
}

function primaryAction() {
  if (albumSupported.value) {
    void saveToAlbum()
  } else {
    download()
  }
}

onMounted(async () => {
  const toy = getToy()
  try {
    albumSupported.value =
      !!toy && typeof toy.isSupport === 'function' && (await toy.isSupport('saveImageToAlbum'))
  } catch {
    albumSupported.value = false
  }
})

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      void generate()
    } else {
      // 关闭时释放预览图 Object URL 与画布，避免隐藏期间持有大图内存
      if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
      previewUrl.value = null
      blob.value = null
      canvas.value = null
      albumSaved.value = false
    }
  },
)

// 组件销毁时释放最后一张预览图的 Object URL，避免泄漏
onUnmounted(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-150"
    >
      <div
        v-if="show"
        class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-ink-950/60 backdrop-blur-sm p-4"
        role="dialog"
        aria-modal="true"
        aria-label="分享结果预览"
        @click.self="close"
      >
        <div
          class="w-full max-w-md max-h-[92vh] flex flex-col rounded-2xl bg-white shadow-2xl overflow-hidden
                 dark:bg-ink-900 ring-1 ring-ink-200/60 dark:ring-ink-700/60 animate-slide-up"
        >
          <!-- 弹窗头 -->
          <div
            class="flex items-center justify-between px-5 py-4 border-b border-ink-200/60 dark:border-ink-700/60"
          >
            <h2 class="font-serif text-base font-semibold text-ink-900 dark:text-ink-100">
              分享结果
            </h2>
            <button
              type="button"
              class="text-sm text-ink-500 hover:text-ink-800 dark:text-ink-400 dark:hover:text-ink-100 transition-colors"
              aria-label="关闭分享预览"
              @click="close"
            >
              ✕ 关闭
            </button>
          </div>

          <!-- 图片预览区（生成中 / 失败 / 成功） -->
          <div class="flex-1 overflow-y-auto bg-ink-100/60 dark:bg-ink-950/60 p-4">
            <div
              v-if="generating"
              class="flex h-64 items-center justify-center flex-col gap-3 text-ink-500 dark:text-ink-400"
              role="status"
            >
              <span
                class="inline-block h-8 w-8 animate-spin rounded-full border-2 border-ink-200 border-t-ember-500"
              />
              <span class="text-sm">正在生成结果图片…</span>
            </div>
            <div
              v-else-if="failed"
              class="flex h-64 items-center justify-center flex-col gap-3 text-ink-500 dark:text-ink-400"
              role="alert"
            >
              <p class="text-sm">图片生成失败，请重试。</p>
              <button type="button" class="btn-ghost !px-4 !py-2 text-sm" @click="generate">
                重试
              </button>
            </div>
            <img
              v-else-if="previewUrl"
              :src="previewUrl"
              alt="结果分享卡片预览"
              class="w-full h-auto rounded-xl shadow-sm ring-1 ring-ink-200/60 dark:ring-ink-700/60"
            />
          </div>

          <!-- 底部操作 -->
          <div class="px-5 py-4 border-t border-ink-200/60 dark:border-ink-700/60">
            <button
              type="button"
              class="btn-primary w-full"
              :disabled="generating || failed || !previewUrl || albumSaving"
              @click="primaryAction"
            >
              <span v-if="albumSaving">保存中…</span>
              <span v-else-if="albumSaved">已保存到相册 ✓</span>
              <span v-else>{{ primaryLabel }}</span>
            </button>
            <button
              v-if="albumSupported"
              type="button"
              class="btn-ghost w-full mt-2"
              :disabled="generating || failed || !previewUrl"
              @click="download"
            >
              下载结果
            </button>
            <p class="mt-3 text-center text-xs text-ink-400 dark:text-ink-500 leading-relaxed">
              卡片在浏览器本地生成，不含题目与原始回答，仅展示倾向与分值。
              <span class="block mt-1 sm:hidden">长按图片也可保存到相册。</span>
            </p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
