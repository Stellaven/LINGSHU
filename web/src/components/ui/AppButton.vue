<script setup lang="ts">
import { LoaderCircle } from '@lucide/vue'

withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
    size?: 'sm' | 'md'
    type?: 'button' | 'submit'
    loading?: boolean
    disabled?: boolean
  }>(),
  { variant: 'secondary', size: 'md', type: 'button', loading: false, disabled: false },
)

const variantClass: Record<string, string> = {
  primary:
    'bg-accent text-white shadow-[0_0_0_1px_rgba(94,106,210,0.5),0_4px_12px_rgba(94,106,210,0.3),inset_0_1px_0_0_rgba(255,255,255,0.2)] hover:bg-accent-bright hover:shadow-[0_0_0_1px_rgba(104,114,217,0.6),0_6px_20px_rgba(94,106,210,0.4),inset_0_1px_0_0_rgba(255,255,255,0.25)]',
  secondary:
    'bg-white/5 text-ink shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)] hover:bg-white/8 hover:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1),0_0_24px_rgba(94,106,210,0.12)]',
  ghost: 'text-muted hover:bg-white/5 hover:text-ink',
  danger:
    'bg-red-500 text-white shadow-[0_0_0_1px_rgba(239,68,68,0.4),0_4px_12px_rgba(239,68,68,0.25)] hover:bg-red-500/90',
}
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="[
      'inline-flex select-none items-center justify-center gap-1.5 rounded-lg font-medium transition-all duration-200 ease-out active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50',
      size === 'sm' ? 'h-8 px-3 text-xs' : 'h-9 px-4 text-sm',
      variantClass[variant],
    ]"
  >
    <LoaderCircle v-if="loading" class="size-4 animate-spin" />
    <slot />
  </button>
</template>
