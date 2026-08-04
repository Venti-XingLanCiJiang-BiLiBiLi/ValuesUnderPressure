<script setup lang="ts">
/**
 * ErrorBoundary — 全局错误边界（#20）
 * ============================================================================
 * 通过 Vue 的 onErrorCaptured 捕获后代组件渲染/生命周期中的错误，
 * 避免整页白屏，并提供一个「重试」按钮让用户自行恢复。
 * 用法：<ErrorBoundary> ...任意内容... </ErrorBoundary>
 * ============================================================================
 */
import { ref, onErrorCaptured } from 'vue'

const error = ref<Error | null>(null)

onErrorCaptured((err) => {
  error.value = err
  // 阻止错误继续向上传播到 Vue 根
  return false
})

function reset() {
  error.value = null
}
</script>

<template>
  <div
    v-if="error"
    class="mx-auto max-w-xl px-6 py-16 text-center"
    role="alert"
    aria-live="assertive"
  >
    <div class="card p-8 sm:p-10">
      <div class="text-4xl mb-3">😵</div>
      <h2 class="font-serif text-xl font-semibold text-ink-900 dark:text-ink-50 mb-2">
        页面出了点问题
      </h2>
      <p class="text-sm text-ink-600 dark:text-ink-300 mb-5 break-all">
        {{ error.message || '发生未知错误' }}
      </p>
      <button type="button" class="btn-primary px-6 py-2" @click="reset">
        重试
      </button>
    </div>
  </div>
  <slot v-else />
</template>
