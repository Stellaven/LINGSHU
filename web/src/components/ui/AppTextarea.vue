<script setup lang="ts">
withDefaults(
  defineProps<{
    placeholder?: string
    rows?: number
    disabled?: boolean
  }>(),
  { rows: 4, disabled: false },
)

const model = defineModel<string>({ default: '' })
</script>

<template>
  <textarea
    v-model="model"
    :placeholder="placeholder"
    :rows="rows"
    :disabled="disabled"
    class="w-full resize-y rounded-lg border border-white/10 bg-input px-3 py-2.5 text-sm leading-relaxed text-ink outline-none transition-all duration-200 placeholder:text-muted/70 focus:border-accent focus:shadow-[0_0_0_3px_rgba(94,106,210,0.25)] disabled:opacity-50"
  />
</template>
