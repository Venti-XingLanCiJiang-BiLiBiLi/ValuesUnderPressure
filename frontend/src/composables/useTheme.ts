/**
 * 主题切换 composable
 * ============================================================================
 * 统一管理 light / dark / system 三种模式。
 *
 * 工作机制：
 * 1. 初始化时从 localStorage 读取（key: quxu:theme），若无则用 'system'
 * 2. 'system' 模式实时监听 matchMedia('(prefers-color-scheme: dark)')
 * 3. 把"实际生效"的主题（light/dark）应用到 <html> 上的 .dark 类
 * 4. 切换 mode 时同步写回 localStorage
 *
 * 用法：
 * ```ts
 * const { mode, resolvedTheme, setMode, toggleMode } = useTheme()
 * ```
 * ============================================================================
 */

import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { THEME_STORAGE_KEY, type ThemeMode } from '@/config/theme'

const STORAGE_KEY = THEME_STORAGE_KEY

export function useTheme() {
  // ---- state ------------------------------------------------------------
  const mode = ref<ThemeMode>('system')
  const systemPrefersDark = ref(false)

  // ---- derived ----------------------------------------------------------
  const resolvedTheme = computed<'light' | 'dark'>(() => {
    if (mode.value === 'system') return systemPrefersDark.value ? 'dark' : 'light'
    return mode.value
  })

  // ---- actions ----------------------------------------------------------
  function setMode(next: ThemeMode) {
    mode.value = next
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // localStorage 不可用（隐私模式/SSR）— 静默忽略
    }
  }

  function toggleMode() {
    // 在 light / dark / system 之间循环
    const order: ThemeMode[] = ['light', 'dark', 'system']
    const idx = order.indexOf(mode.value)
    setMode(order[(idx + 1) % order.length])
  }

  function applyToDom() {
    const root = document.documentElement
    if (resolvedTheme.value === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    // 同步 meta theme-color，避免移动端浏览器 chrome 颜色不匹配
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    if (meta) {
      meta.content = resolvedTheme.value === 'dark' ? '#0f1316' : '#f5f7f8'
    }
  }

  // ---- system theme listener -------------------------------------------
  let mql: MediaQueryList | null = null
  function onSystemChange(e: MediaQueryListEvent) {
    systemPrefersDark.value = e.matches
  }

  onMounted(() => {
    // 1) 读 localStorage
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as ThemeMode | null
      if (saved === 'light' || saved === 'dark' || saved === 'system') {
        mode.value = saved
      }
    } catch {
      // ignore
    }
    // 2) 监听系统主题
    if (typeof window !== 'undefined' && window.matchMedia) {
      mql = window.matchMedia('(prefers-color-scheme: dark)')
      systemPrefersDark.value = mql.matches
      mql.addEventListener('change', onSystemChange)
    }
    // 3) 首次应用
    applyToDom()
  })

  onUnmounted(() => {
    mql?.removeEventListener('change', onSystemChange)
  })

  // mode 变化时同步 DOM
  watch(resolvedTheme, applyToDom)

  return {
    mode,
    resolvedTheme,
    setMode,
    toggleMode,
  }
}
