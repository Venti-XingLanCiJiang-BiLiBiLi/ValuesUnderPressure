/**
 * 结果分享卡片生成（纯浏览器 Canvas 2D，零依赖）
 * ============================================================================
 * 在浏览器端把一份 ResultResponse 渲染成一张品牌风格的结果卡片 PNG，
 * 用于「分享结果」（下载 / 系统分享面板），全程本地完成、不上传任何数据。
 *
 * 设计要点：
 * - 固定使用深色品牌视觉（不受页面亮/暗主题影响），跨平台观感一致；
 * - 逻辑尺寸 540×720，导出时按 scale 放大（默认 2x = 1080×1440），Retina 清晰；
 * - 卡片内容：品牌标题 + 10 维度条（以 50 中线对称展开）+ 底部统计 + 站点水印；
 *   维度条配色阈值与页面结果（DimensionBar）一致（theme.ts SCORE_THRESHOLDS）：
 *   score > 60 → 蓝色渐变、score < 40 → 粉色渐变、其余 → 灰色渐变。
 * ============================================================================
 */
import type { ResultResponse, DimensionScore } from '@/types/api'
import { BRAND } from '@/config/branding'
import { SCORE_THRESHOLDS } from '@/config/theme'

/** 设计稿逻辑尺寸（宽 × 高，导出时按 scale 放大） */
const W = 540
const H = 720
const PAD = 30

/** 色板：与 tailwind.config.js 的 ink / ember 色值对齐（深色卡片专用） */
const C = {
  bgTop: '#0f1316', // ink-950
  bgBottom: '#1f2629', // ink-900
  title: '#ffffff',
  eyebrow: '#fb923c', // ember-400
  sub: '#7a8d96', // ink-400
  line: '#354144', // ink-800
  label: '#e6ecee', // ink-100
  track: '#354144', // ink-800
  center: '#5d717a', // ink-500
  high: ['#3b82f6', '#60a5fa'] as const, // blue-500 -> blue-400
  low: ['#ec4899', '#f472b6'] as const, // pink-500 -> pink-400
  mid: ['#7a8d96', '#a3b3ba'] as const, // ink-400 -> ink-300
  value: '#ffffff',
  muted: '#a3b3ba', // ink-300
  watermark: '#5d717a', // ink-500
} as const

const SANS = '"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif'
const SERIF = '"Source Han Serif SC","Noto Serif CJK SC",Georgia,serif'

export interface ShareCardOptions {
  /** 导出倍率（默认 2 → 1080×1440） */
  scale?: number
}

/** 生成分享卡片 canvas（可继续转 Blob / DataURL） */
export function renderShareCard(
  result: ResultResponse,
  options: ShareCardOptions = {},
): HTMLCanvasElement {
  const scale = options.scale ?? 2
  const canvas = document.createElement('canvas')
  canvas.width = W * scale
  canvas.height = H * scale
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D 上下文不可用')

  ctx.scale(scale, scale)
  drawBackground(ctx)
  drawHeader(ctx)
  drawDimensions(ctx, result)
  drawFooter(ctx, result)
  return canvas
}

/** canvas → PNG Blob */
export function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob)
      else reject(new Error('PNG 编码失败'))
    }, 'image/png')
  })
}

/** 分享文件名：VUP-result-YYYYMMDD.png */
export function shareFileName(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  const stamp = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`
  return `${BRAND.shortName}-result-${stamp}.png`
}

/** 触发浏览器下载（下载按钮与降级路径共用，唯一实现）。 */
export function downloadBlob(blob: Blob) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = shareFileName()
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  // 延迟释放对象 URL，确保下载已开始
  window.setTimeout(() => URL.revokeObjectURL(url), 5000)
}

/* ============================================================================
 * 绘制实现
 * ========================================================================== */

function drawBackground(ctx: CanvasRenderingContext2D) {
  const g = ctx.createLinearGradient(0, 0, 0, H)
  g.addColorStop(0, C.bgTop)
  g.addColorStop(1, C.bgBottom)
  ctx.fillStyle = g
  ctx.fillRect(0, 0, W, H)

  // 顶部暖橘点缀条
  ctx.fillStyle = C.eyebrow
  ctx.fillRect(PAD, 0, 84, 3)
}

/** 带字距文本（手绘字距，跨浏览器一致，不依赖 ctx.letterSpacing） */
function fillTextSpaced(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  spacing: number,
  align: 'left' | 'center' | 'right' = 'left',
) {
  ctx.textBaseline = 'middle'
  ctx.textAlign = align
  const total = text.length > 1 ? (text.length - 1) * spacing : 0
  let startX = x
  if (align === 'center') startX = x - total / 2
  else if (align === 'right') startX = x - total
  for (let i = 0; i < text.length; i++) {
    ctx.fillText(text[i], startX, y)
    startX += ctx.measureText(text[i]).width + spacing
  }
}

function drawHeader(ctx: CanvasRenderingContext2D) {
  // 眉题
  ctx.fillStyle = C.eyebrow
  ctx.font = `500 13px ${SANS}`
  fillTextSpaced(ctx, '你的价值画像', PAD, 62, 6)

  // 品牌名
  ctx.fillStyle = C.title
  ctx.font = `700 34px ${SERIF}`
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText(BRAND.name, PAD, 104)

  // 副标题
  ctx.fillStyle = C.sub
  ctx.font = `400 12px ${SANS}`
  ctx.fillText(`${BRAND.nameEn} · ${BRAND.tagline}`, PAD, 132)

  // 分隔线
  ctx.strokeStyle = C.line
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(PAD, 150)
  ctx.lineTo(W - PAD, 150)
  ctx.stroke()
}

/** 维度区：10 条，按 |score-50| 降序（越极端越靠前，与结果页一致） */
function drawDimensions(ctx: CanvasRenderingContext2D, result: ResultResponse) {
  const dims: DimensionScore[] = Object.values(result.dimensions).sort(
    (a, b) => Math.abs(b.score - 50) - Math.abs(a.score - 50),
  )

  const trackLeft = 170
  const trackRight = W - 90
  const trackWidth = trackRight - trackLeft
  const midX = trackLeft + trackWidth / 2
  const trackHeight = 8
  const rowHeight = 44

  let y = 188
  for (const dim of dims) {
    // 维度名（左）
    ctx.fillStyle = C.label
    ctx.font = `500 14px ${SANS}`
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillText(dim.name, PAD, y, trackLeft - PAD - 8)

    // 分数（右）
    ctx.fillStyle = C.value
    ctx.font = `700 16px ${SANS}`
    ctx.textAlign = 'right'
    ctx.fillText(String(Math.round(dim.score)), W - PAD, y)

    // 条形（50 中线对称展开）
    drawBar(ctx, dim.score, midX, y + 15, trackWidth, trackHeight)

    y += rowHeight
  }
}

/** 以 50 中线向左右展开的对称条形（与页面 DimensionBar 逻辑一致） */
function drawBar(
  ctx: CanvasRenderingContext2D,
  score: number,
  midX: number,
  centerY: number,
  trackWidth: number,
  trackHeight: number,
) {
  const top = centerY - trackHeight / 2
  const radius = trackHeight / 2

  // 轨道
  ctx.fillStyle = C.track
  roundRect(ctx, midX - trackWidth / 2, top, trackWidth, trackHeight, radius)
  ctx.fill()

  // 50 中线标记
  ctx.fillStyle = C.center
  ctx.fillRect(midX - 1, top - 2, 2, trackHeight + 4)

  // 条长 = |score-50|（最大半条 50%，最小 4% 保证可见）
  const pct = Math.max(4, Math.min(50, Math.abs(score - 50))) / 100
  const len = Math.max(11, trackWidth * pct)
  const [deep, shallow] = colorFor(score)

  if (score > 50) {
    // 高分散发：向右，尖端（远离中线端）最深
    const g = ctx.createLinearGradient(midX, 0, midX + len, 0)
    g.addColorStop(0, shallow)
    g.addColorStop(1, deep)
    ctx.fillStyle = g
    roundRect(ctx, midX, top, len, trackHeight, radius)
    ctx.fill()
  } else if (score < 50) {
    // 低分散发：向左，尖端（远离中线端）最深
    const g = ctx.createLinearGradient(midX - len, 0, midX, 0)
    g.addColorStop(0, deep)
    g.addColorStop(1, shallow)
    ctx.fillStyle = g
    roundRect(ctx, midX - len, top, len, trackHeight, radius)
    ctx.fill()
  } else {
    // 恰为 50：居中显示一小段，作为中性标记
    ctx.fillStyle = C.mid[1]
    roundRect(ctx, midX - 6, top, 12, trackHeight, radius)
    ctx.fill()
  }
}

/** 维度条配色：与 theme.ts SCORE_THRESHOLDS（high 60 / low 40）严格对齐 */
function colorFor(score: number): readonly [string, string] {
  if (score > SCORE_THRESHOLDS.high) return C.high
  if (score < SCORE_THRESHOLDS.low) return C.low
  return C.mid
}

function drawFooter(ctx: CanvasRenderingContext2D, result: ResultResponse) {
  // 分隔线
  ctx.strokeStyle = C.line
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(PAD, 636)
  ctx.lineTo(W - PAD, 636)
  ctx.stroke()

  // 三组统计
  const stats = [
    { value: `${result.answered_count} / ${result.total}`, label: '作答进度' },
    { value: `${Math.round((result.confidence ?? 0) * 100)}%`, label: '整体置信度' },
    { value: String(result.conflicts.length), label: '矛盾组合' },
  ]
  const colW = (W - PAD * 2) / 3
  ctx.textBaseline = 'middle'
  stats.forEach((s, i) => {
    const cx = PAD + colW * i + colW / 2
    ctx.textAlign = 'center'
    ctx.fillStyle = C.value
    ctx.font = `700 20px ${SANS}`
    ctx.fillText(s.value, cx, 674)
    ctx.fillStyle = C.sub
    ctx.font = `400 11px ${SANS}`
    ctx.fillText(s.label, cx, 694)
  })

  // 水印
  ctx.textAlign = 'center'
  ctx.fillStyle = C.watermark
  ctx.font = `400 10px ${SANS}`
  ctx.fillText(`${BRAND.name} · ${BRAND.nameEn} · ${BRAND.tagline}`, W / 2, H - 12)
}

/** 圆角矩形路径（手写，兼容未实现 ctx.roundRect 的浏览器） */
function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  const radius = Math.min(r, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.lineTo(x + w - radius, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius)
  ctx.lineTo(x + w, y + h - radius)
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h)
  ctx.lineTo(x + radius, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius)
  ctx.lineTo(x, y + radius)
  ctx.quadraticCurveTo(x, y, x + radius, y)
  ctx.closePath()
}
