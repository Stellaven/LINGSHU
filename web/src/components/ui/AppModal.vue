<script setup lang="ts">
import { X } from '@lucide/vue'
import { onUnmounted, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    /** 弹窗最大宽度（tailwind class） */
    width?: string
  }>(),
  { width: 'max-w-lg' },
)

const emit = defineEmits<{ close: [] }>()

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      document.addEventListener('keydown', onKeydown)
      document.body.style.overflow = 'hidden'
    } else {
      document.removeEventListener('keydown', onKeydown)
      document.body.style.overflow = ''
    }
  },
)

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-50 overflow-y-auto px-4 py-6">
        <!-- 背景遮罩 -->
        <div
          class="fixed inset-0 bg-[#020203]/70 backdrop-blur-sm"
          aria-hidden="true"
          @click="emit('close')"
        />
        <Transition name="zoom" appear>
          <div
            role="dialog"
            aria-modal="true"
            :aria-label="title"
            :class="[
              'relative mx-auto mt-[10vh] w-full rounded-2xl border border-white/8 bg-elevated shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_24px_80px_rgba(0,0,0,0.6)]',
              width,
            ]"
          >
            <!-- 顶部高光渐变线 -->
            <div
              aria-hidden="true"
              class="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-white/15 to-transparent"
            />
            <header class="flex items-center justify-between px-6 py-4">
              <h3 class="text-base font-semibold tracking-tight">{{ title }}</h3>
              <button
                type="button"
                class="flex size-8 items-center justify-center rounded-lg text-muted transition-colors duration-200 hover:bg-white/5 hover:text-ink"
                aria-label="关闭"
                @click="emit('close')"
              >
                <X class="size-4" />
              </button>
            </header>
            <div class="px-6 pb-5">
              <slot />
            </div>
            <footer
              v-if="$slots.footer"
              class="flex items-center justify-end gap-3 border-t border-white/6 px-6 py-4"
            >
              <slot name="footer" />
            </footer>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
