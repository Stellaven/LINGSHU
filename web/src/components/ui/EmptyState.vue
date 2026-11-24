<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div
    class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/12 bg-white/[0.015] px-6 py-16 text-center"
  >
    <div
      class="flex size-12 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-accent/25 to-accent/5 text-accent"
    >
      <slot name="icon" />
    </div>
    <p class="mt-4 text-sm font-medium">{{ title }}</p>
    <p v-if="description" class="mt-1 max-w-sm text-sm text-muted">
      {{ description }}
    </p>
    <div v-if="$slots.action" class="mt-5">
      <slot name="action" />
    </div>
  </div>
</template>
