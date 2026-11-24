<script setup lang="ts">
import { Check } from '@lucide/vue'
import type { Component } from 'vue'

defineProps<{
  name: string
  description: string
  icon: Component
  /** 是否以等宽字体展示名称（解析器/模型名等英文标识） */
  monospace?: boolean
}>()
</script>

<template>
  <div
    class="flex items-start gap-3 rounded-xl border border-accent/40 bg-accent/8 px-4 py-3.5 shadow-[0_0_0_1px_rgba(94,106,210,0.18),0_0_24px_rgba(94,106,210,0.12)]"
  >
    <span
      class="flex size-9 shrink-0 items-center justify-center rounded-lg border border-accent/30 bg-accent/15 text-accent"
    >
      <component :is="icon" class="size-4" :stroke-width="1.75" />
    </span>
    <div class="min-w-0 flex-1">
      <p class="text-xs font-medium text-ink" :class="monospace && 'font-mono'">{{ name }}</p>
      <p class="mt-1 text-xs leading-relaxed text-muted">{{ description }}</p>
    </div>
    <span
      class="ml-auto inline-flex shrink-0 items-center gap-1 rounded-full border border-accent/50 bg-accent/20 px-2 py-0.5 text-[11px] text-accent"
    >
      <Check class="size-3" :stroke-width="2.5" />
      当前
    </span>
  </div>
</template>
