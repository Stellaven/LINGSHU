<script setup lang="ts">
import { LoaderCircle } from '@lucide/vue'

withDefaults(
  defineProps<{
    tone?: 'success' | 'accent' | 'danger'
  }>(),
  { tone: 'success' },
)

const toneClass: Record<string, string> = {
  success: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300',
  accent: 'border-accent/30 bg-accent/10 text-accent',
  danger: 'border-red-400/20 bg-red-400/10 text-red-300',
}
const dotClass: Record<string, string> = {
  success: 'bg-emerald-400',
  accent: 'bg-accent',
  danger: 'bg-red-400',
}
</script>

<template>
  <span
    :class="[
      'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium',
      toneClass[tone],
    ]"
  >
    <LoaderCircle v-if="tone === 'accent'" class="size-3 animate-spin" />
    <span v-else class="size-1.5 rounded-full" :class="dotClass[tone]" />
    <slot />
  </span>
</template>
