<script setup lang="ts">
import { computed, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RoleBadge from '@/components/team/RoleBadge.vue'
import { loaded, myRole, teams } from '@/stores/team'

const route = useRoute()
const router = useRouter()
// 响应式获取：侧边栏切换团队时路由参数变化，页面头部/Tab 需同步更新
const teamId = computed(() => route.params.teamId as string)

const team = computed(() => teams.value.find((t) => t.id === teamId.value) ?? null)
const role = computed(() => myRole(teamId.value))

const TABS = [
  { name: 'team-projects', label: '团队项目', path: 'projects' },
  { name: 'team-members', label: '团队成员', path: 'members' },
  { name: 'team-settings', label: '团队设置', path: 'settings' },
] as const

/**
 * 团队项目：桌面端页面本身不滚动，仅项目列表区域内部滚动。
 * 其余 Tab 保持自然流式布局，页面随内容滚动。
 */
const isListScrollTab = computed(() => route.name === 'team-projects')

// 团队列表由侧边栏负责拉取；硬刷新直接进入本页时等待加载，加载完仍无此团队则回首页
watchEffect(() => {
  if (loaded.value && !team.value) router.replace('/')
})
</script>

<template>
  <!-- 固定高度 = 视口 - 顶栏 3.5rem - main 底部留白 2rem，使页面本身不再滚动 -->
  <div :class="isListScrollTab && 'lg:flex lg:h-[calc(100dvh-5.5rem)] lg:min-h-0 lg:flex-col'">
    <template v-if="team">
      <!-- 顶部：团队名称 + 我的团队身份 -->
      <section class="pt-6 md:pt-8 lg:shrink-0">
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-semibold tracking-tight md:text-3xl">{{ team.name }}</h1>
          <RoleBadge :role="role" />
        </div>
      </section>

      <!-- Tab 导航 -->
      <nav class="mt-6 flex items-center gap-1 border-b border-white/6 lg:shrink-0">
        <RouterLink
          v-for="tab in TABS"
          :key="tab.name"
          :to="`/team/${teamId}/${tab.path}`"
          class="relative px-3 py-2.5 text-sm transition-colors"
          :class="route.name === tab.name ? 'font-medium text-ink' : 'text-muted hover:text-ink'"
        >
          {{ tab.label }}
          <span
            v-if="route.name === tab.name"
            class="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent"
          />
        </RouterLink>
      </nav>

      <section class="pt-7" :class="isListScrollTab && 'lg:min-h-0 lg:flex-1 lg:overflow-hidden'">
        <!-- key 绑定团队 ID：切换团队时强制重建面板，避免面板内固化旧 teamId 的数据 -->
        <RouterView :key="teamId" />
      </section>
    </template>

    <!-- 硬刷新时的加载骨架 -->
    <div v-else class="pt-6 md:pt-8">
      <div class="h-8 w-40 animate-pulse rounded-lg bg-white/5" />
    </div>
  </div>
</template>
