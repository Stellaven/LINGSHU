<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Users } from '@lucide/vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { ensureTeams, teams } from '@/stores/team'

/**
 * 首页（登录后默认入口）：
 * 有团队 → 重定向到第一个团队详情页；无团队 → 空状态引导。
 */
const router = useRouter()
const loading = ref(true)

async function resolveHome() {
  await ensureTeams()
  if (teams.value.length) {
    await router.replace(`/team/${teams.value[0].id}/projects`)
  } else {
    loading.value = false
  }
}

onMounted(() => {
  void resolveHome()
})

// 停留在空状态期间创建了首个团队 → 立即离开空状态（仅空状态展示中响应）。
// 注意监听数量而非数组引用：store 的 createTeam 是原地 push，引用不变
watch(
  () => teams.value.length,
  (len) => {
    if (!loading.value && len) {
      void router.replace(`/team/${teams.value[0].id}/projects`)
    }
  },
)
</script>

<template>
  <div class="pt-6 md:pt-8">
    <div v-if="loading" class="flex h-64 items-center justify-center">
      <span
        class="size-6 animate-spin rounded-full border-2 border-white/15 border-t-accent"
        role="status"
        aria-label="加载中"
      />
    </div>
    <EmptyState v-else title="当前没有团队" description="请新建团队或者加入其他团队">
      <template #icon>
        <Users class="size-5" />
      </template>
    </EmptyState>
  </div>
</template>
