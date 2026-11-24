<script setup lang="ts">
import { computed, onMounted, provide, ref, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BackButton from '@/components/BackButton.vue'
import RoleBadge from '@/components/team/RoleBadge.vue'
import { projectContextKey } from '@/components/project/context'
import * as api from '@/api/project'
import type { ProjectRole, ProjectView } from '@/types/team'

const route = useRoute()
const router = useRouter()
// 响应式获取：路由参数变化时页面头部/Tab 需同步更新
const teamId = computed(() => route.params.teamId as string)
const projectId = computed(() => route.params.projectId as string)

const project = ref<ProjectView | null>(null)
const myRole = ref<ProjectRole>('member')
const gone = ref(false)

// 项目信息与我的角色供各 Tab 面板共享
provide(projectContextKey, { project, myRole })

onMounted(async () => {
  try {
    const [p, me] = await Promise.all([
      api.getProject(projectId.value),
      api.getMyProjectMembership(projectId.value),
    ])
    project.value = p
    myRole.value = me.role
  } catch {
    gone.value = true
  }
})

// 项目不存在（如硬刷新到已解散的项目）→ 回团队项目列表
watchEffect(() => {
  if (gone.value) router.replace(`/team/${teamId.value}/projects`)
})

const TABS = [
  { name: 'project-kbs', label: '项目知识库', path: 'kbs' },
  { name: 'project-members', label: '项目成员', path: 'members' },
  { name: 'project-models', label: '模型配置', path: 'models' },
  { name: 'project-settings', label: '项目设置', path: 'settings' },
] as const

/**
 * 知识库 / 模型配置：桌面端页面本身不滚动，仅内容列表区域内部滚动。
 * 其余 Tab 保持自然流式布局，页面随内容滚动。
 */
const isListScrollTab = computed(
  () => route.name === 'project-kbs' || route.name === 'project-models',
)
</script>

<template>
  <!-- 固定高度 = 视口 - 顶栏 3.5rem - main 底部留白 2rem，使页面本身不再滚动 -->
  <div :class="isListScrollTab && 'lg:flex lg:h-[calc(100dvh-5.5rem)] lg:min-h-0 lg:flex-col'">
    <template v-if="project">
      <!-- 返回 -->
      <section class="pt-6 md:pt-8 lg:shrink-0">
        <BackButton :to="`/team/${teamId}/projects`" />
      </section>

      <!-- 顶部：项目名称 + 我的项目身份 -->
      <section class="mt-3 lg:shrink-0">
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-semibold tracking-tight md:text-3xl">{{ project.name }}</h1>
          <RoleBadge kind="project" :role="myRole" />
        </div>
      </section>

      <!-- Tab 导航 -->
      <nav class="mt-6 flex items-center gap-1 border-b border-white/6 lg:shrink-0">
        <RouterLink
          v-for="tab in TABS"
          :key="tab.name"
          :to="`/team/${teamId}/project/${projectId}/${tab.path}`"
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
        <!-- key 绑定项目 ID：切换项目时强制重建面板，避免面板内固化旧 projectId 的数据 -->
        <RouterView :key="projectId" />
      </section>
    </template>

    <!-- 硬刷新时的加载骨架 -->
    <div v-else class="pt-6 md:pt-8">
      <div class="h-8 w-40 animate-pulse rounded-lg bg-white/5" />
    </div>
  </div>
</template>
