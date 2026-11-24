<script setup lang="ts">
import { ArrowUpDown, Check, ChevronDown, Folder, GripVertical, Plus, User, Users } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as api from '@/api/team'
import { myRole } from '@/stores/team'
import type { ProjectView } from '@/types/team'
import CreateProjectModal from '@/components/team/CreateProjectModal.vue'
import AppButton from '@/components/ui/AppButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'

type SortMode = 'name-asc' | 'name-desc' | 'created-asc' | 'created-desc' | 'custom'

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
  { value: 'name-asc', label: '按名称升序' },
  { value: 'name-desc', label: '按名称降序' },
  { value: 'created-asc', label: '按创建时间升序' },
  { value: 'created-desc', label: '按创建时间降序' },
  { value: 'custom', label: '自定义排序（可拖拽）' },
]

const route = useRoute()
const router = useRouter()
const teamId = route.params.teamId as string

/** 点击卡片进入项目详情页 */
function openProject(project: ProjectView) {
  router.push(`/team/${teamId}/project/${project.id}`)
}

const projects = ref<ProjectView[]>([])
const loading = ref(true)
const sortMode = ref<SortMode>('custom')
const sortOpen = ref(false)
const createOpen = ref(false)

// 仅团队所有者可新建项目
const isTeamOwner = computed(() => myRole(teamId) === 'owner')

onMounted(async () => {
  projects.value = await api.listProjects(teamId)
  loading.value = false
})

const displayed = computed(() => {
  const list = [...projects.value]
  switch (sortMode.value) {
    case 'name-asc':
      return list.sort((a, b) => a.name.localeCompare(b.name, 'zh'))
    case 'name-desc':
      return list.sort((a, b) => b.name.localeCompare(a.name, 'zh'))
    case 'created-asc':
      return list.sort((a, b) => a.createdAt.localeCompare(b.createdAt))
    case 'created-desc':
      return list.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    default:
      return list.sort((a, b) => a.sortOrder - b.sortOrder)
  }
})

const sortLabel = computed(() => SORT_OPTIONS.find((o) => o.value === sortMode.value)?.label ?? '排序')
const isCustom = computed(() => sortMode.value === 'custom')

/** ---------------- 拖拽排序（仅自定义模式可用） ---------------- */

const dragIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)

function onDragStart(index: number) {
  if (!isCustom.value) return
  dragIndex.value = index
}

function onDragEnter(index: number) {
  if (dragIndex.value === null) return
  dragOverIndex.value = index
}

async function onDrop() {
  const from = dragIndex.value
  const to = dragOverIndex.value
  dragIndex.value = null
  dragOverIndex.value = null
  if (from === null || to === null || from === to) return
  const list = displayed.value.slice()
  const [moved] = list.splice(from, 1)
  list.splice(to, 0, moved)
  const orderedIds = list.map((p) => p.id)
  await api.updateProjectOrder(teamId, orderedIds)
  projects.value = projects.value.map((p) => ({ ...p, sortOrder: orderedIds.indexOf(p.id) + 1 }))
}

function selectSort(value: SortMode) {
  sortMode.value = value
  sortOpen.value = false
}

function clearDrag() {
  dragIndex.value = null
  dragOverIndex.value = null
}

function onCreated(project: ProjectView) {
  projects.value.push(project)
}
</script>

<template>
  <div class="lg:flex lg:h-full lg:min-h-0 lg:flex-col">
    <!-- 工具栏：排序 + 新建项目 -->
    <section class="flex flex-wrap items-center gap-3 pb-6 lg:shrink-0">
      <div class="relative">
        <button
          type="button"
          class="flex h-9 items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-muted transition-colors hover:text-ink"
          @click="sortOpen = !sortOpen"
        >
          <ArrowUpDown class="size-4" />
          {{ sortLabel }}
          <ChevronDown class="size-3.5 transition-transform" :class="sortOpen && 'rotate-180'" />
        </button>
        <div v-if="sortOpen" class="fixed inset-0 z-20" @click="sortOpen = false" />
        <div
          v-if="sortOpen"
          class="absolute left-0 top-full z-30 mt-1.5 w-52 rounded-xl border border-white/10 bg-elevated p-1 shadow-[0_12px_40px_rgba(0,0,0,0.5)]"
        >
          <button
            v-for="opt in SORT_OPTIONS"
            :key="opt.value"
            type="button"
            class="flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors"
            :class="opt.value === sortMode ? 'text-ink' : 'text-muted hover:bg-white/5 hover:text-ink'"
            @click="selectSort(opt.value)"
          >
            {{ opt.label }}
            <Check v-if="opt.value === sortMode" class="size-3.5 text-accent" />
          </button>
        </div>
      </div>
      <span v-if="isCustom" class="text-xs text-muted">拖拽卡片可调整顺序</span>
      <AppButton v-if="isTeamOwner" variant="primary" class="ml-auto" @click="createOpen = true">
        <Plus class="size-4" />
        新建项目
      </AppButton>
    </section>

    <!-- 骨架屏 -->
    <section
      v-if="loading"
      v-scroll-auto-hide
      class="scroll-auto-hide grid grid-cols-1 gap-5 sm:grid-cols-2 lg:min-h-0 lg:flex-1 lg:auto-rows-max lg:grid-cols-3 lg:overflow-y-auto lg:pr-2 xl:grid-cols-4"
      aria-busy="true"
    >
      <div v-for="i in 3" :key="i" class="card-surface h-44 animate-pulse p-5">
        <div class="flex items-center gap-3">
          <div class="size-10 shrink-0 rounded-xl bg-white/5" />
          <div class="h-4 w-1/2 rounded bg-white/5" />
        </div>
        <div class="mt-4 h-3 w-full rounded bg-white/5" />
        <div class="mt-2 h-3 w-2/3 rounded bg-white/5" />
      </div>
    </section>

    <!-- 项目卡片网格：桌面端仅列表区域滚动 -->
    <section
      v-else-if="displayed.length"
      v-scroll-auto-hide
      class="scroll-auto-hide grid grid-cols-1 gap-5 sm:grid-cols-2 lg:min-h-0 lg:flex-1 lg:auto-rows-max lg:grid-cols-3 lg:overflow-y-auto lg:pr-2 xl:grid-cols-4"
    >
      <article
        v-for="(project, i) in displayed"
        :key="project.id"
        v-spotlight
        :draggable="isCustom"
        class="card-surface spotlight group relative overflow-hidden p-5 transition-all duration-300 ease-out hover:-translate-y-1 hover:border-white/10 hover:shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_12px_40px_rgba(0,0,0,0.5),0_0_60px_rgba(94,106,210,0.12)]"
        :class="[
          'cursor-pointer',
          dragIndex === i && 'opacity-40',
          dragOverIndex === i && dragIndex !== null && dragIndex !== i && 'ring-2 ring-accent',
        ]"
        @dragstart="onDragStart(i)"
        @dragenter="onDragEnter(i)"
        @dragover.prevent
        @drop.prevent="onDrop"
        @dragend="clearDrag"
        @click="openProject(project)"
      >
        <GripVertical
          v-if="isCustom"
          class="absolute right-3 top-3 size-4 text-muted opacity-0 transition-opacity group-hover:opacity-100"
        />
        <div class="flex items-center gap-3 pr-5">
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-accent/30 to-accent/5 text-accent"
          >
            <Folder class="size-5" :stroke-width="1.75" />
          </div>
          <h3 class="min-w-0 flex-1 truncate text-[15px] font-semibold tracking-tight">
            {{ project.name }}
          </h3>
        </div>
        <p
          class="mt-4 line-clamp-2 min-h-10 text-sm leading-relaxed text-muted"
          :title="project.description || undefined"
        >
          {{ project.description || '暂无描述' }}
        </p>
        <div class="mt-4 flex items-center gap-4 border-t border-white/6 pt-4 text-xs text-muted">
          <span class="inline-flex items-center gap-1.5">
            <User class="size-3.5" />
            {{ project.ownerName }}
          </span>
          <span class="inline-flex items-center gap-1.5">
            <Users class="size-3.5" />
            {{ project.memberCount }} 人
          </span>
        </div>
      </article>
    </section>

    <!-- 空状态 -->
    <section v-else>
      <EmptyState
        title="还没有项目"
        :description="isTeamOwner ? '创建第一个项目，开始团队协作。' : '团队所有者尚未创建项目。'"
      >
        <template #icon><Folder class="size-6" :stroke-width="1.5" /></template>
        <template v-if="isTeamOwner" #action>
          <AppButton variant="primary" @click="createOpen = true">
            <Plus class="size-4" />
            新建项目
          </AppButton>
        </template>
      </EmptyState>
    </section>

    <CreateProjectModal
      :open="createOpen"
      :team-id="teamId"
      @close="createOpen = false"
      @created="onCreated"
    />
  </div>
</template>
