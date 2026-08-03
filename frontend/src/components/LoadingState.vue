<script setup lang="ts">
/**
 * LoadingState — 通用加载态
 */
withDefaults(
  defineProps<{
    label?: string
    size?: 'sm' | 'md' | 'lg'
  }>(),
  { label: '加载中…', size: 'md' },
)
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 gap-3">
    <div
      class="inline-block animate-spin rounded-full border-2 border-ink-200 border-t-ember-500
             dark:border-ink-700"
      :class="{
        'h-6 w-6': size === 'sm',
        'h-10 w-10': size === 'md',
        'h-14 w-14': size === 'lg',
      }"
    />
    <p v-if="label" class="text-sm text-ink-500 dark:text-ink-400">{{ label }}</p>
  </div>
</template>
