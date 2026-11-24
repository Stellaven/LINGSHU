<script setup lang="ts">
import { ChevronDown, Plus, Users } from '@lucide/vue'
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LogoMark from '@/components/LogoMark.vue'
import CreateTeamModal from '@/components/CreateTeamModal.vue'
import UserMenu from '@/components/UserMenu.vue'
import { ensureTeams, selectTeam, selectedTeam, teams } from '@/stores/team'

const expanded = ref(true)
const createOpen = ref(false)

const route = useRoute()
const router = useRouter()

// 团队详情页刷新/回退时，让侧边栏选中态与路由保持同步
watch(
  () => route.params.teamId,
  (id) => {
    if (typeof id === 'string' && id) selectTeam(id)
  },
  { immediate: true },
)

onMounted(() => {
  void ensureTeams()
})

function openTeam(id: string) {
  selectTeam(id)
  router.push(`/team/${id}`)
}
</script>

<template>
  <aside
    class="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-white/6 bg-base/70 backdrop-blur-xl md:flex"
  >
    <!-- 品牌区：LOGO + LINGSHU（纯展示，不可点击） -->
    <div class="flex h-14 shrink-0 items-center gap-2.5 border-b border-white/6 px-5">
      <LogoMark class="size-8 rounded-lg" />
      <span class="text-sm font-semibold tracking-[0.18em]">LINGSHU</span>
    </div>

    <!-- 我的团队 -->
    <nav class="flex-1 overflow-y-auto p-3">
      <button
        type="button"
        class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium text-ink transition-colors hover:bg-white/5"
        :aria-expanded="expanded"
        @click="expanded = !expanded"
      >
        <Users class="size-4 text-muted" />
        我的团队
        <ChevronDown
          class="ml-auto size-4 text-muted transition-transform duration-200"
          :class="expanded ? 'rotate-0' : '-rotate-90'"
        />
      </button>

      <!-- 团队列表（展开时显示） -->
      <ul v-show="expanded" class="ml-6 mt-1 space-y-0.5">
        <li v-for="team in teams" :key="team.id">
          <button
            type="button"
            class="w-full rounded-lg px-2 py-1.5 text-left text-sm transition-colors"
            :class="
              team.id === selectedTeam?.id
                ? 'bg-white/8 text-ink'
                : 'text-muted hover:bg-white/5 hover:text-ink'
            "
            @click="openTeam(team.id)"
          >
            {{ team.name }}
          </button>
        </li>
        <li>
          <button
            type="button"
            class="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-accent transition-colors hover:bg-white/5 hover:text-accent-bright"
            @click="createOpen = true"
          >
            <Plus class="size-4" />
            新建团队
          </button>
        </li>
      </ul>

      <!-- 模型配置已移入项目详情页的「模型配置」Tab，侧边栏不再提供全局入口 -->
    </nav>

    <!-- 底部：当前登录用户菜单（向上展开；移动端侧边栏不可见，由顶栏提供入口） -->
    <div class="shrink-0 border-t border-white/6 p-3">
      <UserMenu direction="up" />
    </div>

    <CreateTeamModal :open="createOpen" @close="createOpen = false" />
  </aside>
</template>
