<script setup lang="ts">
/**
 * ProgressBar — 通用进度条
 * 受控组件，由父组件传入 current/total。
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    current: number
    total: number
    showLabel?: boolean
  }>(),
  { showLabel: true },
)

const percent = computed(() => {
  if (props.total === 0) return 0
  return Math.round((props.current / props.total) * 100)
})
</script>

<template>
  <div>
    <div
      v-if="showLabel"
      class="flex items-center justify-between mb-2 text-sm text-ink-600 dark:text-ink-400"
    >
      <span>进度</span>
      <span class="font-mono tabular-nums">{{ current }} / {{ total }}</span>
    </div>
    <div class="h-2 w-full rounded-full bg-ink-200 dark:bg-ink-800 overflow-hidden">
      <div
        class="h-full bg-gradient-to-r from-ember-500 to-ember-400 transition-all duration-500 ease-out"
        :style="{ width: `${percent}%` }"
      />
    </div>
  </div>
</template>
