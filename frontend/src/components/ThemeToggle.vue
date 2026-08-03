<script setup lang="ts">
/**
 * ThemeToggle — 主题切换按钮
 * --------------------------------------------------------------------------
 * 三态循环：light → dark → system → light ...
 * system 模式下显示月亮图标 + 半个 A 字（"auto"）
 */
import { useTheme } from '@/composables/useTheme'
import type { ThemeMode } from '@/config/theme'

const { mode, setMode } = useTheme()

const OPTIONS: { value: ThemeMode; label: string; icon: string }[] = [
  { value: 'light', label: '浅色', icon: '☀️' },
  { value: 'dark', label: '深色', icon: '🌙' },
  { value: 'system', label: '跟随系统', icon: '💻' },
]
</script>

<template>
  <div
    class="inline-flex items-center rounded-full bg-ink-100 dark:bg-ink-800 p-0.5 ring-1 ring-ink-200 dark:ring-ink-700"
    role="radiogroup"
    aria-label="主题切换"
  >
    <button
      v-for="opt in OPTIONS"
      :key="opt.value"
      type="button"
      role="radio"
      :aria-checked="mode === opt.value"
      :title="opt.label"
      class="px-2 py-1 text-sm rounded-full transition-all"
      :class="
        mode === opt.value
          ? 'bg-white dark:bg-ink-700 shadow-sm'
          : 'opacity-60 hover:opacity-100'
      "
      @click="setMode(opt.value)"
    >
      <span aria-hidden="true">{{ opt.icon }}</span>
      <span class="sr-only">{{ opt.label }}</span>
    </button>
  </div>
</template>
