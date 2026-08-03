<script setup lang="ts">
/**
 * ConflictCard — 矛盾组合提示卡
 * 展示两个高分维度同时出现时的张力分析。
 */
import type { ConflictItem } from '@/types/api'

defineProps<{ conflict: ConflictItem }>()
</script>

<template>
  <div
    class="rounded-2xl border border-amber-200 bg-amber-50/70 p-5
           dark:border-amber-700/40 dark:bg-amber-950/30"
  >
    <div class="flex items-start gap-3">
      <div class="shrink-0 mt-0.5">
        <svg
          class="h-5 w-5 text-amber-600 dark:text-amber-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex flex-wrap items-baseline gap-x-2 gap-y-1 mb-1.5">
          <span class="font-serif text-base font-semibold text-amber-900 dark:text-amber-200">
            {{ conflict.names[0] }}
          </span>
          <span class="text-amber-700 dark:text-amber-500 text-sm">×</span>
          <span class="font-serif text-base font-semibold text-amber-900 dark:text-amber-200">
            {{ conflict.names[1] }}
          </span>
        </div>
        <p class="text-sm text-amber-900/80 dark:text-amber-200/80 leading-relaxed">
          {{ conflict.description }}
        </p>
      </div>
    </div>
  </div>
</template>
