<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    disabled?: boolean
  }>(),
  { disabled: false },
)

const model = defineModel<boolean>({ default: false })

const checked = computed(() => model.value)

function onToggle() {
  if (!props.disabled) model.value = !model.value
}
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="checked"
    :disabled="disabled"
    class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-200 disabled:pointer-events-none disabled:opacity-50"
    :class="checked ? 'bg-accent' : 'bg-white/10'"
    @click="onToggle"
  >
    <span
      class="absolute left-0.5 size-4 rounded-full bg-white shadow-[0_1px_3px_rgba(0,0,0,0.4)] transition-transform duration-200"
      :class="checked && 'translate-x-4'"
    />
  </button>
</template>
