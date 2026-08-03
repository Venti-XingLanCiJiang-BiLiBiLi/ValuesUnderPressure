/**
 * 品牌配置
 * ============================================================================
 * 集中管理产品品牌信息（中文名 / 英文名 / 标语 / Logo 等）。
 *
 * 整个应用任何需要展示品牌文案的地方都从这里 import，
 * 避免"取舍之间"、"Values Under Pressure"、"VUP" 在不同文件里写散。
 *
 * 修改品牌名时，只需改本文件。
 * ============================================================================
 */

export const BRAND = {
  /** 主品牌名（中文） */
  name: '取舍之间',
  /** 副品牌名（英文） */
  nameEn: 'Values Under Pressure',
  /** 缩写 */
  shortName: 'VUP',
  /** 顶部小字 */
  tagline: '不是人格分类，只描述倾向。',
  /** 页脚副标题 */
  footerNote: '结果只描述倾向，不做人格定性。允许矛盾。',
  /** OpenAPI 兼容的官网/仓库（展示用） */
  siteUrl: 'https://github.com/Venti-XingLanCiJiang-BiLiBiLi/ValuesUnderPressure',
} as const

export type BrandKey = keyof typeof BRAND
