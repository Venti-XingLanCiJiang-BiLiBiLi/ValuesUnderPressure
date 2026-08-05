<script setup lang="ts">
/**
 * ResultContent — 结果内容展示（纯展示组件）
 * --------------------------------------------------------------------------
 * 接收一份 ResultResponse，渲染：
 * 顶部概览三卡（进度 / 置信度 / 矛盾数）
 * 中部 10 维度按偏离中间值 50 的绝对值降序排列（越极端越靠前）
 * 底部矛盾分析 + 不确定维度提示
 *
 * 同时被结果页 ResultView 与存档页 ArchiveView 复用，
 * 保证两处结果展示一致。
 */
import { computed } from 'vue'
import type { DimensionMeta, DimensionScore, ResultResponse } from '@/types/api'
import { BRAND } from '@/config/branding'
import { useDimensionMeta } from '@/composables/useDimensionMeta'
import DimensionBar from '@/components/DimensionBar.vue'
import ConflictCard from '@/components/ConflictCard.vue'

const props = defineProps<{ result: ResultResponse }>()

// 维度元数据（来自题库 dimensions.json，单一数据源）：高分/低分表现标签与描述。
// 拉取失败（后端不可用）时保持 null，DimensionBar 自动降级为不展示两端标签。
const { meta, load } = useDimensionMeta()
void load()

// 按 |score - 50| 降序排序：偏离中间值 50 越远（越极端）排在最前，
// 最贴近 50 的排在最后。结合"条长 = 偏差"，页面顶部展示最强的倾向。
const sortedDimensions = computed<DimensionScore[]>(() =>
  Object.values(props.result.dimensions).sort(
    (a, b) => Math.abs(b.score - 50) - Math.abs(a.score - 50),
  ),
)

const confidencePercent = computed(() =>
  Math.round((props.result.confidence ?? 0) * 100),
)

/**
 * 面向用户展示的维度名统一用中文标签：
 * 优先取结果对象内的 name（后端由题库 label 填充），
 * 缺失（旧存档）时回退到维度元数据 label，再兜底显示英文 id 本身。
 */
function dimensionLabel(dimId: string): string {
  const scored = props.result.dimensions[dimId]
  if (scored?.name) return scored.name
  return meta.value?.[dimId]?.label ?? dimId
}

const uncertainLabels = computed(() =>
  props.result.uncertain_dimensions.map(dimensionLabel),
)

function metaOf(dimId: string): DimensionMeta | null {
  return meta.value?.[dimId] ?? null
}
</script>

<template>
  <!-- ============================== Header ============================== -->
  <div class="text-center mb-10 animate-fade-in">
    <p class="text-xs uppercase tracking-[0.3em] text-ember-600 dark:text-ember-400 mb-3">
      你的价值画像
    </p>
    <h1
      class="font-serif text-3xl sm:text-4xl font-semibold text-ink-900 dark:text-ink-50 mb-4"
    >
      {{ BRAND.name }}
    </h1>
    <p class="text-ink-600 dark:text-ink-300 text-base max-w-md mx-auto">
      以下是
      <strong class="text-ink-900 dark:text-ink-100">{{ result.answered_count }}</strong>
      道题中你的倾向分布。
      结果只描述倾向，不做人格定性。
    </p>
  </div>

  <!-- ============================== 概览 ============================== -->
  <div class="grid sm:grid-cols-3 gap-3 mb-8">
    <div class="card p-4 text-center">
      <p class="text-xs text-ink-500 dark:text-ink-400 mb-1">作答进度</p>
      <p class="font-mono text-2xl text-ink-900 dark:text-ink-100 tabular-nums">
        {{ result.answered_count }} / {{ result.total }}
      </p>
    </div>
    <div class="card p-4 text-center">
      <p class="text-xs text-ink-500 dark:text-ink-400 mb-1">整体置信度</p>
      <p class="font-mono text-2xl text-ink-900 dark:text-ink-100 tabular-nums">
        {{ confidencePercent }}%
      </p>
    </div>
    <div class="card p-4 text-center">
      <p class="text-xs text-ink-500 dark:text-ink-400 mb-1">矛盾组合</p>
      <p class="font-mono text-2xl text-ink-900 dark:text-ink-100 tabular-nums">
        {{ result.conflicts.length }}
      </p>
    </div>
  </div>

  <!-- ============================== 维度列表 ============================== -->
  <h2 class="font-serif text-2xl font-semibold text-ink-900 dark:text-ink-100 mb-4 mt-10">
    10 个价值维度
  </h2>
  <div class="space-y-3 mb-10">
    <DimensionBar
      v-for="(dim, idx) in sortedDimensions"
      :key="dim.dimension"
      :dim="dim"
      :meta="metaOf(dim.dimension)"
      :rank="idx + 1"
    />
  </div>

  <!-- ============================== 矛盾分析 ============================== -->
  <div v-if="result.conflicts.length > 0" class="mt-12">
    <h2 class="font-serif text-2xl font-semibold text-ink-900 dark:text-ink-100 mb-2">
      矛盾分析
    </h2>
    <p class="text-sm text-ink-600 dark:text-ink-300 mb-5 leading-relaxed">
      你的回答在以下维度组合上同时表现强烈——这不是错误，恰恰是真实的你。
      价值之间的张力，本身就是人之为人的复杂度。
    </p>
    <div class="space-y-3">
      <ConflictCard
        v-for="(c, i) in result.conflicts"
        :key="i"
        :conflict="c"
      />
    </div>
  </div>

  <!-- ============================== 不确定维度 ============================== -->
  <div
    v-if="result.uncertain_dimensions.length > 0"
    class="mt-10 rounded-2xl border border-ink-200 bg-ink-50 p-5
           dark:border-ink-700 dark:bg-ink-900/60"
  >
    <h3 class="font-serif text-base font-semibold text-ink-900 dark:text-ink-100 mb-2">
      作答一致性偏低的维度
    </h3>
    <p class="text-sm text-ink-600 dark:text-ink-300 leading-relaxed">
      以下维度在不同题目间的作答方向不一致，可能受具体情境影响较大：
      <span class="text-ink-900 dark:text-ink-100 font-medium ml-1">
        {{ uncertainLabels.join('、') }}
      </span>
    </p>
  </div>
</template>
