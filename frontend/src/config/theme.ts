/**
 * 主题配置
 * ============================================================================
 * 集中管理颜色、过渡时长、动画曲线等设计 token。
 *
 * 颜色分为两套：light（亮色）和 dark（暗色）。
 * Tailwind 通过 darkMode: 'class' 切换 .dark 根类。
 *
 * 注意：实际颜色仍然在 tailwind.config.js 的 theme.extend.colors 里定义，
 * 本文件只做语义映射（哪个场景用哪个色阶），避免组件里到处写
 * "bg-ink-50 dark:bg-ink-950" 这种重复表达式。
 * ============================================================================
 */

/** 主题模式 */
export type ThemeMode = 'light' | 'dark' | 'system'

/** 主题存储 key（localStorage） */
export const THEME_STORAGE_KEY = 'quxu:theme'

/**
 * 评分阈值：用于结果页维度条配色
 * - score >= HIGH_THRESHOLD: 暖色（高分倾向）
 * - score <= LOW_THRESHOLD: 冷色（低分倾向）
 * - 其他: 中性色
 */
export const SCORE_THRESHOLDS = {
  high: 70,
  low: 30,
} as const

/**
 * 一致性阈值：用于结果页一致性标签
 * - >= 0.8: 稳定倾向（绿）
 * - >= 0.6: 较为稳定（中性）
 * - <  0.6: 情境依赖（琥珀）
 * - null:  数据不足（灰）
 */
export const CONSISTENCY_THRESHOLDS = {
  stable: 0.8,
  moderate: 0.6,
} as const

/** 动画时长（毫秒） */
export const ANIMATION = {
  fast: 150,
  base: 300,
  slow: 500,
} as const
