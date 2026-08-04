import { onMounted, onUnmounted } from 'vue'

/**
 * 答题键盘快捷键（#19）
 * ============================================================================
 * 在挂载时注册全局 keydown 监听，卸载时移除。
 * 按键映射（与视觉提示一致）：
 *   Y / →        → onYes
 *   N / ←        → onNo
 *   ↑ / Backspace → onBack
 *   ↓            → onNext
 * 规则：
 * - 焦点在输入框（INPUT / TEXTAREA / SELECT）时不触发，避免干扰输入；
 * - 长按连发（e.repeat）不触发，防止按住 Y 连续答多题；
 * - 触发时 preventDefault，避免 Backspace 触发浏览器后退。
 * ============================================================================
 */

export interface KeyboardShortcutHandlers {
  onYes?: () => void
  onNo?: () => void
  onBack?: () => void
  onNext?: () => void
}

export function useKeyboardShortcuts(handlers: KeyboardShortcutHandlers) {
  function handleKeydown(e: KeyboardEvent) {
    // 长按连发不触发
    if (e.repeat) return
    // 避免在输入框等场景触发
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement)?.tagName)) {
      return
    }

    switch (e.key.toLowerCase()) {
      case 'y':
      case 'arrowright':
        e.preventDefault()
        handlers.onYes?.()
        break
      case 'n':
      case 'arrowleft':
        e.preventDefault()
        handlers.onNo?.()
        break
      case 'arrowup':
      case 'backspace':
        e.preventDefault()
        handlers.onBack?.()
        break
      case 'arrowdown':
        e.preventDefault()
        handlers.onNext?.()
        break
    }
  }

  onMounted(() => window.addEventListener('keydown', handleKeydown))
  onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
}
