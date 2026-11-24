/**
 * v-spotlight — 鼠标追踪光斑指令
 * 用法：在卡片元素上添加 v-spotlight，鼠标划过时出现跟随光标的环境光。
 * 样式见 styles/main.css 中 .spotlight 规则。
 */
import type { Directive } from 'vue'

interface SpotlightEl extends HTMLElement {
  __spotlightCleanup?: () => void
}

export const vSpotlight: Directive<SpotlightEl> = {
  mounted(el) {
    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect()
      el.style.setProperty('--spot-x', `${e.clientX - rect.left}px`)
      el.style.setProperty('--spot-y', `${e.clientY - rect.top}px`)
    }
    el.addEventListener('mousemove', onMove)
    el.__spotlightCleanup = () => el.removeEventListener('mousemove', onMove)
  },
  unmounted(el) {
    el.__spotlightCleanup?.()
  },
}
