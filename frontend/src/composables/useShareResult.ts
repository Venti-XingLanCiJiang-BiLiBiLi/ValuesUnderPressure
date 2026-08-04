/**
 * 结果分享（浏览器端完成，零后端依赖）
 * ============================================================================
 * 把一份 ResultResponse 渲染成 PNG 结果卡片并引导用户保存/分享：
 * 1) 优先使用 Web Share API —— 移动端现代浏览器会弹出系统分享面板，
 *    可直接「存储图像 / 分享到微信 / 微博 / 邮件」；
 * 2) 不支持时降级为触发浏览器下载（桌面端主流）。
 *
 * 全程在浏览器本地生成，不上传任何结果数据、不引入后端 share 端点。
 * 用户取消系统分享面板（AbortError）视为正常取消，不算失败。
 * ============================================================================
 */
import { ref } from 'vue'
import type { ResultResponse } from '@/types/api'
import { BRAND } from '@/config/branding'
import { renderShareCard, canvasToBlob } from '@/utils/shareCard'

export type SharePhase = 'idle' | 'generating' | 'ready' | 'error'

const MOBILE_RE = /Android|iPhone|iPad|iPod|Mobile/i

export function useShareResult() {
  /** 分享流程状态：idle 待触发 / generating 生成中 / ready 已生成(下载完成) / error 失败 */
  const phase = ref<SharePhase>('idle')

  /** 是否为移动/触摸设备（用于选择引导文案：系统分享 vs 下载） */
  const isMobile = ref(
    typeof navigator !== 'undefined' && MOBILE_RE.test(navigator.userAgent),
  )

  /**
   * 生成并分享结果卡片。
   * @returns true 表示已进入分享/下载；false 表示用户取消或失败（看 phase）
   */
  async function share(result: ResultResponse): Promise<boolean> {
    phase.value = 'generating'
    try {
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
  }

  function scheduleReset() {
    window.setTimeout(reset, 2500)
  }

  return { phase, isMobile, share, reset }
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
