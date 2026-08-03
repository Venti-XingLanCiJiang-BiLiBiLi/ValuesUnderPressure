<script setup lang="ts">
/**
 * DimensionBar — 单个维度评分条
 * --------------------------------------------------------------------------
 * 显示：排名 #、维度名、分数 (0-100)、条形可视化、倾向文案、一致性标签。
 *
 * 条形以 50 为中线向左右两侧展开（对称条形图）：
 * 低分向左、高分向右，条长 = 偏离中值 50 的程度（|score-50|，最大半条 50%），
 * 越贴近 50 条越短，越偏向极端条越长。
 *
 * 配色策略：
 * - score > SCORE_THRESHOLDS.high (60) → 蓝色渐变（高分倾向）
 * - score < SCORE_THRESHOLDS.low  (40) → 粉色渐变（低分倾向）
 * - 40 ~ 60                            → 灰色渐变（中间）
 *
 * 一致性配色：
 * - >= 0.8 : 稳定倾向（绿）
 * - >= 0.6 : 较为稳定（中性）
 * - <  0.6 : 情境依赖（琥珀）
 * - null   : 数据不足（灰）
 */
import { computed } from 'vue'
import type { DimensionScore } from '@/types/api'
import { SCORE_THRESHOLDS, CONSISTENCY_THRESHOLDS } from '@/config/theme'

const props = defineProps<{ dim: DimensionScore; rank?: number }>()

// 条形以 50 中线向两侧展开：低分向左、高分向右。
// 条长 = 偏离程度 |score-50|（最大占半条 50%）；给最小 4% 保证 50 分时仍可见。
const barStyle = computed(() => {
  const d = Math.abs(props.dim.score - 50)
  const width = Math.max(4, Math.min(50, d))
  if (props.dim.score > 50) return { left: '50%', width: `${width}%` }
  if (props.dim.score < 50) return { left: `${50 - width}%`, width: `${width}%` }
  // 正好 50：居中显示一小段，作为中性标记
  return { left: `${50 - width / 2}%`, width: `${width}%` }
})

// 渐变方向：让远离中线的尖端颜色最深、向中线渐浅
const barGradient = computed(() =>
  props.dim.score < 50 ? 'bg-gradient-to-r' : 'bg-gradient-to-l',
)

const barColor = computed(() => {
  const s = props.dim.score
  if (s > SCORE_THRESHOLDS.high) return 'from-blue-500 to-blue-400'
  if (s < SCORE_THRESHOLDS.low) return 'from-pink-500 to-pink-400'
  return 'from-ink-500 to-ink-400 dark:from-ink-400 dark:to-ink-300'
})

const consistencyText = computed(() => {
  const c = props.dim.consistency
  if (c === null || c === undefined) return '数据不足'
  if (c >= CONSISTENCY_THRESHOLDS.stable) return '稳定倾向'
  if (c >= CONSISTENCY_THRESHOLDS.moderate) return '较为稳定'
  return '情境依赖'
})

const consistencyColor = computed(() => {
  const c = props.dim.consistency
  if (c === null || c === undefined) return 'text-ink-400'
  if (c >= CONSISTENCY_THRESHOLDS.stable) return 'text-emerald-600 dark:text-emerald-400'
  if (c >= CONSISTENCY_THRESHOLDS.moderate) return 'text-ink-600 dark:text-ink-300'
  return 'text-amber-600 dark:text-amber-400'
})
</script>

<template>
  <div class="card p-5">
    <div class="flex items-baseline justify-between mb-2 gap-3">
      <div class="flex items-baseline gap-2 min-w-0">
        <span v-if="rank" class="text-xs font-mono text-ink-400 tabular-nums">#{{ rank }}</span>
        <h3 class="font-serif text-lg font-semibold text-ink-900 dark:text-ink-100 truncate">
          {{ dim.name }}
        </h3>
      </div>
      <span class="font-mono text-2xl tabular-nums text-ink-900 dark:text-ink-100">
        {{ Math.round(dim.score) }}
      </span>
    </div>

    <div
      class="relative h-3 w-full rounded-full bg-ink-100 dark:bg-ink-800 overflow-hidden mb-3"
    >
      <!-- 50 中线标记 -->
      <div
        class="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-ink-300/80 dark:bg-ink-600/80"
      />
      <!-- 从 50 中线向左右两侧展开的条 -->
      <div
        class="absolute top-0 h-full transition-all duration-700 ease-out"
        :class="[barGradient, barColor]"
        :style="barStyle"
      />
    </div>

    <p class="text-sm text-ink-700 dark:text-ink-300 leading-relaxed mb-3">
      {{ dim.description }}
    </p>

    <div class="flex items-center justify-between text-xs">
      <span class="inline-flex items-center gap-1.5">
        <span class="text-ink-500 dark:text-ink-400">倾向</span>
        <span class="font-medium text-ink-800 dark:text-ink-200">{{ dim.tendency }}</span>
      </span>
      <span class="inline-flex items-center gap-1.5">
        <span class="text-ink-500 dark:text-ink-400">一致性</span>
        <span class="font-medium" :class="consistencyColor">
          {{ consistencyText
          }}<span
            v-if="dim.consistency !== null"
            class="ml-0.5 text-ink-400"
          >{{ Math.round(dim.consistency * 100) }}%</span>
        </span>
      </span>
    </div>
  </div>
</template>
