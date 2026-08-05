/**
 * 结果分享（浏览器端完成，零后端依赖）
 * ============================================================================
 * 把一份 ResultResponse 渲染成 PNG 结果卡片并引导用户保存/分享：
 * 0) B站 App（Toy 环境）→ 优先用 toy.saveImageToAlbum 保存到系统相册；
 * 1) 移动端浏览器 → Web Share API 弹出系统分享面板；
 * 2) 桌面端 → 降级为触发浏览器下载。
 *
 * 全程在浏览器本地生成，不上传任何结果数据、不引入后端 share 端点。
 * 用户取消系统分享面板（AbortError）视为正常取消，不算失败。
 * ============================================================================
 */
import { ref } from 'vue'
import type { ResultResponse } from '@/types/api'
import { BRAND } from '@/config/branding'
import { getToy } from '@/composables/useToy'
import { renderShareCard, canvasToBlob } from '@/utils/shareCard'

export type SharePhase = 'idle' | 'generating' | 'ready' | 'error'

/** 本次操作实际使用的保存方式（用于结果页提示文案）。 */
export type ShareMode = 'album' | 'share' | 'download' | null

const MOBILE_RE = /Android|iPhone|iPad|iPod|Mobile/i

/** saveImageToAlbum 的 base64 上限为 2M，预留 10% 余量。 */
const MAX_ALBUM_BASE64 = 1.8 * 1024 * 1024

export function useShareResult() {
  /** 分享流程状态：idle 待触发 / generating 生成中 / ready 已生成(下载完成) / error 失败 */
  const phase = ref<SharePhase>('idle')

  /** 本次分享实际采用的保存方式（album = B站 App 相册） */
  const mode = ref<ShareMode>(null)

  /** 是否为移动/触摸设备（用于选择引导文案：系统分享 vs 下载） */
  const isMobile = ref(
    typeof navigator !== 'undefined' && MOBILE_RE.test(navigator.userAgent),
  )

  /**
   * 生成并分享结果卡片。
   * @returns true 表示已进入分享/下载/保存；false 表示用户取消或失败（看 phase）
   */
  async function share(result: ResultResponse): Promise<boolean> {
    phase.value = 'generating'
    mode.value = null
    try {
      // 0) B站 App：保存到系统相册（Toy SDK，需用户手势触发）
      const toy = getToy()
      if (toy && typeof toy.isSupport === 'function' && (await toy.isSupport('saveImageToAlbum'))) {
        await saveToAlbum(toy, result)
        phase.value = 'ready'
        mode.value = 'album'
        scheduleReset()
        return true
      }

      const canvas = renderShareCard(result)
      const blob = await canvasToBlob(canvas)
      const file = new File([blob], shareFileName(), { type: 'image/png' })

      // 1) 系统分享面板（含图片文件）
      if (
        typeof navigator.share === 'function' &&
        navigator.canShare?.({ files: [file] })
      ) {
        await navigator.share({
          files: [file],
          title: '我的价值画像',
          text: `${BRAND.name} · ${BRAND.tagline}`,
        })
        phase.value = 'idle'
        return true
      }

      // 2) 降级：触发浏览器下载
      downloadBlob(blob)
      phase.value = 'ready'
      mode.value = 'download'
      scheduleReset()
      return true
    } catch (err) {
      // 用户主动取消分享面板不算失败
      if (err instanceof DOMException && err.name === 'AbortError') {
        phase.value = 'idle'
        return false
      }
      phase.value = 'error'
      return false
    }
  }

  function reset() {
    phase.value = 'idle'
    mode.value = null
  }

  function scheduleReset() {
    window.setTimeout(reset, 2500)
  }

  return { phase, mode, isMobile, share, reset }
}

/**
 * B站 App 内保存结果卡片到系统相册。
 * base64 超过 SDK 上限（2M）时自动降级：先 JPEG 压缩，仍超则用 1x 尺寸重渲染。
 */
async function saveToAlbum(
  toy: ToySDK.Toy,
  result: ResultResponse,
): Promise<void> {
  let dataUrl = renderShareCard(result).toDataURL('image/png')
  if (dataUrl.length > MAX_ALBUM_BASE64) {
    dataUrl = renderShareCard(result).toDataURL('image/jpeg', 0.9)
  }
  if (dataUrl.length > MAX_ALBUM_BASE64) {
    dataUrl = renderShareCard(result, { scale: 1 }).toDataURL('image/jpeg', 0.85)
  }
  // SDK 字段为裸 base64 数据（不含 data:...;base64, 前缀）
  const base64Data = dataUrl.slice(dataUrl.indexOf(',') + 1)
  await toy.saveImageToAlbum({
    base64Data,
    hintMsg: '需要相册权限来保存你的结果卡片',
  })
}

/** 分享文件名：VUP-result-YYYYMMDD.png */
function shareFileName(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  const stamp = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`
  return `${BRAND.shortName}-result-${stamp}.png`
}

function downloadBlob(blob: Blob) {
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
