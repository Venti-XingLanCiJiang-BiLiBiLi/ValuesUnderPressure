/**
 * Toy SDK 访问封装
 * ============================================================================
 * window.toy 由 Toy 平台 SDK（index.html 中的 toy-sdk.js）注入；
 * 非 Toy 环境（本地开发 / 普通浏览器 / GitHub Pages）下 window.toy 不存在，
 * 本模块统一做判空兜底，调用方无需关心环境差异。
 * ============================================================================
 */

/** 获取 window.toy 实例（不存在时返回 null）。 */
export function getToy(): ToySDK.Toy | null {
  if (typeof window === 'undefined') return null
  return window.toy ?? null
}

/**
 * 判断当前环境是否支持指定 Toy 能力（安全兜底）。
 * 非 Toy 环境 / SDK 未加载时返回 false，不会抛错。
 */
export async function isToySupported(ability: string): Promise<boolean> {
  const toy = getToy()
  if (!toy || typeof toy.isSupport !== 'function') return false
  try {
    return await toy.isSupport(ability)
  } catch {
    return false
  }
}
