<script setup lang="ts">
withDefaults(
  defineProps<{
    placeholder?: string
    type?: string
    disabled?: boolean
  }>(),
  { type: 'text', disabled: false },
)

const model = defineModel<string>({ default: '' })
</script>

<template>
  <input
    v-model="model"
    :type="type"
    :placeholder="placeholder"
    :disabled="disabled"
    class="h-9 w-full rounded-lg border border-white/10 bg-input px-3 text-sm text-ink outline-none transition-all duration-200 placeholder:text-muted/70 focus:border-accent focus:shadow-[0_0_0_3px_rgba(94,106,210,0.25)] disabled:opacity-50"
  />
</template>
