/**
 * 维度元数据 composable（模块级缓存，多页面共享）
 * ============================================================================
 * 数据源：本地引擎 getDimensions ← 题库 question-bank/<version>/dimensions.json。
 * 前端不维护任何维度名称/描述的副本，只在渲染时按 dimension id 关联元数据。
 *
 * 模块级单例 + 请求去重：结果页 / 存档页 / 开屏页多次进入只请求一次；
 * 拉取失败时返回 null，调用方自行降级（隐藏依赖元数据的展示块）。
 * ============================================================================
 */
import { ref } from 'vue'
import { testApi } from '@/api/client'
import type { DimensionMeta } from '@/types/api'

const meta = ref<Record<string, DimensionMeta> | null>(null)
const loading = ref(false)
let loaded = false

export function useDimensionMeta() {
  /** 拉取一次维度元数据（幂等：已加载则直接返回缓存）。 */
  async function load(force = false): Promise<Record<string, DimensionMeta> | null> {
    if (loaded && !force) return meta.value
    if (loading.value) return meta.value
    loading.value = true
    try {
      meta.value = await testApi.getDimensions()
      loaded = true
    } catch (e) {
      // 不可用时静默失败，调用方用 `meta` 判空降级
      console.warn('[useDimensionMeta] 拉取维度元数据失败：', e)
    } finally {
      loading.value = false
    }
    return meta.value
  }

  return { meta, loading, load }
}
