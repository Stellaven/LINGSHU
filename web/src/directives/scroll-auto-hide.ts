/**
 * v-scroll-auto-hide — 滚动条自动隐藏指令
 * 用法：在可滚动容器上同时添加 v-scroll-auto-hide 与 scroll-auto-hide 类。
 * 滚动时显示滚动条，停止滚动约 800ms 后自动隐藏（样式见 styles/main.css）。
 */
import type { Directive } from 'vue'

/** 停止滚动后隐藏滚动条的延迟（ms） */
const HIDE_DELAY = 800

interface ScrollAutoHideEl extends HTMLElement {
  __scrollAutoHideCleanup?: () => void
}

export const vScrollAutoHide: Directive<ScrollAutoHideEl> = {
  mounted(el) {
    let timer: number | undefined

    const onScroll = () => {
      el.classList.add('is-scrolling')
      window.clearTimeout(timer)
      timer = window.setTimeout(() => {
        el.classList.remove('is-scrolling')
      }, HIDE_DELAY)
    }

    el.addEventListener('scroll', onScroll, { passive: true })
    el.__scrollAutoHideCleanup = () => {
      window.clearTimeout(timer)
      el.removeEventListener('scroll', onScroll)
      el.classList.remove('is-scrolling')
    }
  },
  unmounted(el) {
    el.__scrollAutoHideCleanup?.()
  },
}
