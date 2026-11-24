<script setup lang="ts">
import { ChevronDown, KeyRound, LogOut } from '@lucide/vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ChangePasswordModal from '@/components/ChangePasswordModal.vue'
import { currentUser, logout } from '@/stores/auth'

/**
 * 账号菜单：头像 + 账号名 + 下拉（修改密码 / 退出登录）。
 * - direction="down"：顶栏使用，菜单向下展开
 * - direction="up"：侧边栏底部使用，菜单向上展开
 * 点击菜单外部关闭：采用 document 级监听（不使用 fixed 遮罩，
 * 避免父级 backdrop-filter 改变 fixed 定位基准导致遮罩范围异常）。
 */
const props = withDefaults(defineProps<{ direction?: 'up' | 'down' }>(), { direction: 'down' })

const router = useRouter()
const menuOpen = ref(false)
const pwdOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const chevronClass = computed(() =>
  props.direction === 'up'
    ? menuOpen.value
      ? 'rotate-0'
      : 'rotate-180'
    : menuOpen.value
      ? 'rotate-180'
      : 'rotate-0',
)

function onDocumentClick(e: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) menuOpen.value = false
}

watch(menuOpen, (open) => {
  if (open) document.addEventListener('click', onDocumentClick)
  else document.removeEventListener('click', onDocumentClick)
})

onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))

async function onLogout() {
  menuOpen.value = false
  await logout()
  router.replace('/login')
}

function openChangePassword() {
  menuOpen.value = false
  pwdOpen.value = true
}
</script>

<template>
  <div v-if="currentUser" ref="rootRef" class="relative">
    <button
      type="button"
      class="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 py-1 pl-1 pr-2.5 transition-colors hover:border-white/20 hover:bg-white/10"
      @click="menuOpen = !menuOpen"
    >
      <span
        class="flex size-6 shrink-0 items-center justify-center rounded-full border border-accent/40 bg-accent/20 text-[10px] font-semibold text-accent"
      >
        {{ currentUser.account.slice(0, 1).toUpperCase() }}
      </span>
      <span class="max-w-28 truncate text-xs text-muted">{{ currentUser.account }}</span>
      <ChevronDown class="size-3.5 shrink-0 text-muted transition-transform duration-200" :class="chevronClass" />
    </button>

    <div
      v-if="menuOpen"
      class="absolute z-30 w-44 rounded-xl border border-white/10 bg-elevated p-1 shadow-[0_12px_40px_rgba(0,0,0,0.5)]"
      :class="direction === 'up' ? 'bottom-full left-0 mb-1.5' : 'right-0 top-full mt-1.5'"
    >
      <button
        type="button"
        class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-white/5 hover:text-ink"
        @click="openChangePassword"
      >
        <KeyRound class="size-4" />
        修改密码
      </button>
      <button
        type="button"
        class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-red-400 transition-colors hover:bg-red-500/10"
        @click="onLogout"
      >
        <LogOut class="size-4" />
        退出登录
      </button>
    </div>
  </div>

  <ChangePasswordModal :open="pwdOpen" @close="pwdOpen = false" />
</template>
