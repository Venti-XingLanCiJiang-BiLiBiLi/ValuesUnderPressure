/**
 * 维度元数据（前端本地副本）
 * ============================================================================
 * 10 个核心价值维度的元数据。前端在结果页用作"维度名 → 颜色 / 图标"映射，
 * 以及"分数 → 倾向文案"的回退（当后端 description 为空时）。
 *
 * **权威源**：`backend/app/dimensions.py`（后端）/ `docs/DimensionSystem.md`
 * 后端会通过 `GET /api/dimensions` 返回完整元数据，本文件仅做前端展示层
 * 需要的样式映射，避免每个组件都写一份 switch。
 *
 * 保持本文件与 `backend/app/dimensions.py` 的 DIMENSIONS 字典 ID 一致。
 *
 * @deprecated DIMENSION_BAR_COLOR 和 DIMENSION_EMOJI 是纯前端样式映射，
 *   不应由后端生成。如需新增维度，请同时更新此文件和后端 dimensions.py。
 * ============================================================================
 */

export type DimensionId =
  | 'self_protection'
  | 'altruism'
  | 'freedom'
  | 'security'
  | 'privacy'
  | 'wealth'
  | 'rule_orientation'
  | 'pragmatism'
  | 'collectivism'
  | 'long_term'

/**
 * @deprecated 纯前端样式映射，颜色/emoji 属于展示层，不应由后端生成。
 *   保留仅为兼容现有组件，新代码请直接使用 Tailwind class。
 */
export const DIMENSION_BAR_COLOR: Record<DimensionId, string> = {
  self_protection: 'from-rose-500 to-rose-400',
  altruism: 'from-emerald-500 to-emerald-400',
  freedom: 'from-sky-500 to-sky-400',
  security: 'from-amber-500 to-amber-400',
  privacy: 'from-violet-500 to-violet-400',
  wealth: 'from-yellow-500 to-yellow-400',
  rule_orientation: 'from-blue-500 to-blue-400',
  pragmatism: 'from-orange-500 to-orange-400',
  collectivism: 'from-teal-500 to-teal-400',
  long_term: 'from-indigo-500 to-indigo-400',
}

/**
 * @deprecated 纯前端样式映射，颜色/emoji 属于展示层，不应由后端生成。
 *   保留仅为兼容现有组件，新代码请直接使用 emoji 字面量。
 */
export const DIMENSION_EMOJI: Record<DimensionId, string> = {
  self_protection: '🛡️',
  altruism: '🤝',
  freedom: '🕊️',
  security: '🔒',
  privacy: '👁️',
  wealth: '💰',
  rule_orientation: '⚖️',
  pragmatism: '🎯',
  collectivism: '👥',
  long_term: '🌱',
}
