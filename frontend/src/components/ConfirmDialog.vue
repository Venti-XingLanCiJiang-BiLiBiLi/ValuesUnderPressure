<script setup lang="ts">
import { withDefaults, defineProps, defineEmits } from 'vue'

const props = withDefaults(defineProps<{
  show: boolean
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
}>(), {
  title: '提示',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
})

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'confirm'): void
}>()

function close() {
  emit('update:show', false)
}

function doConfirm() {
  emit('confirm')
  emit('update:show', false)
}
</script>

<template>
  <div v-if="props.show" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/40" @click="close" />
    <div class="card p-6 relative z-10 w-full max-w-sm">
      <h3 class="text-lg font-medium text-ink-900 dark:text-ink-50 mb-2">{{ props.title }}</h3>
      <p v-if="props.message" class="text-sm text-ink-700 dark:text-ink-300 mb-4">{{ props.message }}</p>
      <div class="flex justify-end gap-3">
        <button type="button" class="btn-ghost px-4 py-2" @click="close">{{ props.cancelText }}</button>
        <button type="button" class="btn-n px-4 py-2" @click="doConfirm">{{ props.confirmText }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 确认对话样式依赖全局设计系统（btn/btn-ghost/btn-n/card） */
</style>
