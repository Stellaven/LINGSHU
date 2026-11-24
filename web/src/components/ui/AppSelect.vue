<script setup lang="ts">
import { Check, ChevronDown } from '@lucide/vue'
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 关联的 label 元素 for 属性 */
    id?: string
    options: { value: string; label: string }[]
    placeholder?: string
    disabled?: boolean
    /** 尺寸：md = 表单默认（h-9），sm = 行内紧凑（h-8） */
    size?: 'sm' | 'md'
  }>(),
  { id: undefined, placeholder: '请选择', disabled: false, size: 'md' },
)

const model = defineModel<string>({ default: '' })

const open = ref(false)
const selected = computed(() => props.options.find((opt) => opt.value === model.value))
const display = computed(() => selected.value?.label ?? props.placeholder)

function toggle() {
  if (props.disabled) return
  open.value = !open.value
}

function select(value: string) {
  model.value = value
  open.value = false
}
</script>

<template>
  <div class="relative">
    <button
      :id="props.id"
      type="button"
      class="flex w-full items-center gap-2 rounded-lg border border-white/10 bg-input px-3 text-left outline-none transition-all duration-200 focus:border-accent focus:shadow-[0_0_0_3px_rgba(94,106,210,0.25)] disabled:cursor-not-allowed disabled:opacity-50"
      :class="props.size === 'sm' ? 'h-8 text-xs' : 'h-9 text-sm'"
      :disabled="props.disabled"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="toggle"
    >
      <span class="min-w-0 flex-1 truncate" :class="selected ? 'text-ink' : 'text-muted/70'">
        {{ display }}
      </span>
      <ChevronDown
        class="size-4 shrink-0 text-muted transition-transform duration-200"
        :class="open && 'rotate-180'"
      />
    </button>

    <!-- 点击下拉框外部关闭 -->
    <div v-if="open" class="fixed inset-0 z-30" @click="open = false" />

    <div
      v-if="open"
      role="listbox"
      class="absolute left-0 top-full z-40 mt-1.5 max-h-60 w-full overflow-y-auto rounded-xl border border-white/10 bg-elevated p-1 shadow-[0_12px_40px_rgba(0,0,0,0.5)]"
    >
      <p v-if="!props.options.length" class="px-3 py-2 text-xs text-muted">暂无可选项</p>
      <button
        v-for="opt in props.options"
        :key="opt.value"
        type="button"
        role="option"
        class="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition-colors"
        :class="[
          props.size === 'sm' ? 'text-xs' : 'text-sm',
          opt.value === model ? 'text-ink' : 'text-muted hover:bg-white/5 hover:text-ink',
        ]"
        :aria-selected="opt.value === model"
        @click="select(opt.value)"
      >
        <span class="min-w-0 truncate" :title="opt.label">{{ opt.label }}</span>
        <Check v-if="opt.value === model" class="size-3.5 shrink-0 text-accent" />
      </button>
    </div>
  </div>
</template>
