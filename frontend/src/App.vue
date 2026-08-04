<script setup lang="ts">
/**
 * App.vue — 应用根组件
 * ============================================================================
 * 职责：
 * 1. 布局骨架（header / main / footer）
 * 2. 主题初始化（useTheme 在 mount 时读 localStorage 并应用到 <html>）
 * 3. 页面切换过渡动画（vue RouterView + Transition）
 * 4. 自动恢复上次的答题会话（useSessionRestore）
 * ============================================================================
 */
import { onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import { useSessionRestore } from '@/composables/useSessionRestore'
import { useTestStore } from '@/stores/test'
import { BRAND } from '@/config/branding'
import ThemeToggle from '@/components/ThemeToggle.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'

const route = useRoute()
useTheme() // 副作用：mount 时初始化主题

const store = useTestStore()
const { tryRestore, loadCachedResult } = useSessionRestore()

onMounted(async () => {
  if (route.name === 'intro' || route.name === 'test') {
    // 尝试恢复进行中的答题会话
    const restored = await tryRestore()
    if (restored) {
      store.hydrate({
        sessionId: restored.sessionId,
        total: restored.total,
      })
    }
  } else if (route.name === 'result') {
    // 结果页刷新：从 sessionStorage 恢复缓存结果（无需后端）
    const cached = loadCachedResult()
    if (cached) {
      store.restoreFromCache(cached.sessionId, cached.result)
    }
  }
})
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <!-- ============================== Header ============================== -->
    <header
      class="border-b border-ink-200/60 bg-white/80 backdrop-blur sticky top-0 z-10
             dark:border-ink-800 dark:bg-ink-950/80"
    >
      <div class="mx-auto max-w-3xl px-6 py-4 flex items-center justify-between gap-3">
        <RouterLink
          to="/"
          class="flex items-center gap-2 text-ink-900 hover:text-ember-500 transition-colors
                 dark:text-ink-100"
        >
          <svg viewBox="0 0 64 64" class="h-7 w-7" fill="none" aria-hidden="true">
            <rect width="64" height="64" rx="14" fill="currentColor" class="text-ink-900 dark:text-ink-100" />
            <path
              d="M14 18 L32 46 L50 18"
              stroke="#f97316"
              stroke-width="4"
              stroke-linecap="round"
              stroke-linejoin="round"
              fill="none"
            />
            <circle cx="32" cy="46" r="3" fill="#f97316" />
          </svg>
          <span class="font-serif text-lg font-semibold tracking-wide">
            {{ BRAND.name }}
          </span>
        </RouterLink>
        <div class="flex items-center gap-3">
          <span class="text-xs text-ink-500 hidden sm:inline">{{ BRAND.nameEn }}</span>
          <ThemeToggle />
        </div>
      </div>
    </header>

    <!-- ============================== Main ============================== -->
    <main class="flex-1">
      <!-- #20：全局错误边界，避免后代组件异常导致整页白屏 -->
      <ErrorBoundary>
        <RouterView v-slot="{ Component, route: r }">
          <Transition
            mode="out-in"
            enter-active-class="transition-all duration-300 ease-out"
            leave-active-class="transition-all duration-200 ease-in"
            enter-from-class="opacity-0 translate-y-2"
            leave-to-class="opacity-0 -translate-y-2"
          >
            <component :is="Component" :key="r.path" />
          </Transition>
        </RouterView>
      </ErrorBoundary>
    </main>

    <!-- ============================== Footer ============================== -->
    <footer class="border-t border-ink-200/60 py-6 dark:border-ink-800">
      <div class="mx-auto max-w-3xl px-6 text-center text-xs text-ink-500 dark:text-ink-400">
        <p>{{ BRAND.name }} · {{ BRAND.nameEn }}</p>
        <p class="mt-1">{{ BRAND.footerNote }}</p>
      </div>
    </footer>
  </div>
</template>
