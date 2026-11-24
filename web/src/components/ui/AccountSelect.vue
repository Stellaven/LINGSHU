/**
 * 账号搜索选择器：只能从搜索结果中选择，不能手动输入提交。
 * 输入即防抖搜索（由 fetcher 决定候选来源），键盘上下/回车/Esc 可用。
 */
<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

interface AccountOption {
  /** 登录账号 */
  account: string
  /** 展示昵称（缺省回退账号） */
  nickname?: string
}

const props = defineProps<{
  /** 候选来源：传入搜索关键词，返回候选账号列表 */
  fetcher: (query: string) => Promise<AccountOption[]>
  placeholder?: string
}>()

const selected = defineModel<AccountOption | null>({ default: null })

const DEBOUNCE_MS = 300

const text = ref('')
const options = ref<AccountOption[]>([])
const loading = ref(false)
const open = ref(false)
const highlight = ref(0)

let seq = 0
let timer: ReturnType<typeof setTimeout> | null = null

async function doSearch(query: string) {
  const current = ++seq
  loading.value = true
  try {
    const rows = await props.fetcher(query)
    if (current !== seq) return
    options.value = rows
    highlight.value = 0
    open.value = true
  } finally {
    if (current === seq) loading.value = false
  }
}

function scheduleSearch() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => doSearch(text.value), DEBOUNCE_MS)
}

// 手动输入即取消已选状态（只能选择，选中的账号被编辑后视为重新搜索）
watch(text, (val) => {
  if (selected.value && val !== optionLabel(selected.value)) {
    selected.value = null
  }
  scheduleSearch()
})

function optionLabel(option: AccountOption): string {
  return option.nickname || option.account
}

function pick(option: AccountOption) {
  selected.value = option
  text.value = optionLabel(option)
  open.value = false
}

function onInputFocus() {
  // 首次聚焦/重新打开时拉取默认候选列表
  if (!open.value) doSearch(text.value)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault()
    if (!open.value || options.value.length === 0) return
    const delta = e.key === 'ArrowDown' ? 1 : -1
    highlight.value = (highlight.value + delta + options.value.length) % options.value.length
  } else if (e.key === 'Enter') {
    // 阻止冒泡触发外层表单提交
    e.preventDefault()
    if (open.value && options.value[highlight.value]) pick(options.value[highlight.value])
  } else if (e.key === 'Escape') {
    open.value = false
  }
}

const rootRef = ref<HTMLElement | null>(null)
function onDocMousedown(e: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) open.value = false
}
onMounted(() => document.addEventListener('mousedown', onDocMousedown))
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocMousedown)
  if (timer) clearTimeout(timer)
})
</script>

<template>
  <div ref="rootRef" class="relative">
    <input
      v-model="text"
      type="text"
      :placeholder="placeholder"
      class="h-9 w-full rounded-lg border border-white/10 bg-input px-3 text-sm text-ink outline-none transition-all duration-200 placeholder:text-muted/70 focus:border-accent focus:shadow-[0_0_0_3px_rgba(94,106,210,0.25)]"
      autocomplete="off"
      @focus="onInputFocus"
      @keydown="onKeydown"
    />
    <!-- 已选标记 -->
    <span
      v-if="selected"
      class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-accent"
    >
      已选择
    </span>

    <div
      v-if="open"
      class="absolute z-30 mt-1.5 max-h-60 w-full overflow-auto rounded-lg border border-white/10 bg-elevated py-1 shadow-xl"
    >
      <p v-if="loading" class="px-3 py-2.5 text-sm text-muted">搜索中…</p>
      <p v-else-if="options.length === 0" class="px-3 py-2.5 text-sm text-muted">
        未找到匹配的账号
      </p>
      <button
        v-for="(option, i) in options"
        v-else
        :key="option.account"
        type="button"
        class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors"
        :class="i === highlight ? 'bg-accent/15 text-ink' : 'text-ink hover:bg-white/5'"
        @mousedown.prevent
        @click="pick(option)"
        @mousemove="highlight = i"
      >
        <span class="truncate">{{ optionLabel(option) }}</span>
        <span
          v-if="option.nickname && option.nickname !== option.account"
          class="truncate font-mono text-xs text-muted"
        >
          {{ option.account }}
        </span>
      </button>
    </div>
  </div>
</template>
