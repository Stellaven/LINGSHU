<script setup lang="ts" generic="T extends string">
import { Check } from '@lucide/vue'
import type { StrategyOption } from './options'

const props = defineProps<{
  modelValue: T
  options: StrategyOption<T>[]
  label: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: T]
}>()
</script>

<template>
  <div class="grid grid-cols-1 gap-2 sm:grid-cols-2" role="radiogroup" :aria-label="props.label">
    <button
      v-for="opt in props.options"
      :key="opt.value"
      type="button"
      role="radio"
      :aria-checked="props.modelValue === opt.value"
      class="group flex w-full items-start gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-all duration-200 ease-out"
      :class="
        props.modelValue === opt.value
          ? 'border-accent/40 bg-accent/8 shadow-[0_0_0_1px_rgba(94,106,210,0.18),0_0_24px_rgba(94,106,210,0.12)]'
          : 'border-white/8 bg-white/[0.02] hover:border-white/14 hover:bg-white/[0.04]'
      "
      @click="emit('update:modelValue', opt.value)"
    >
      <span
        class="flex size-8 shrink-0 items-center justify-center rounded-lg border transition-colors duration-200"
        :class="
          props.modelValue === opt.value
            ? 'border-accent/30 bg-accent/15 text-accent'
            : 'border-white/10 bg-white/[0.03] text-muted group-hover:text-ink'
        "
      >
        <component :is="opt.icon" class="size-4" :stroke-width="1.75" />
      </span>
      <span class="min-w-0 flex-1">
        <span class="block truncate text-xs font-medium text-ink" :class="opt.monospace && 'font-mono'">
          {{ opt.name }}
        </span>
        <span class="mt-0.5 block text-[11px] leading-relaxed text-muted">
          {{ opt.description }}
        </span>
      </span>
      <span
        class="flex size-4 shrink-0 items-center justify-center rounded-full border transition-colors duration-200"
        :class="
          props.modelValue === opt.value
            ? 'border-accent/50 bg-accent/20 text-accent'
            : 'border-white/10 text-transparent'
        "
      >
        <Check class="size-2.5" :stroke-width="2.5" />
      </span>
    </button>
  </div>
</template>
