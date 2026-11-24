<script setup lang="ts">
import { ArrowUpDown, BookOpen, Check, ChevronDown, Cpu, Files, GripVertical, Plus, Trash2 } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import * as api from '@/api/project'
import { deleteKnowledgeBase } from '@/api/knowledge'
import type { KnowledgeBase } from '@/types/knowledge'
import CreateKnowledgeBaseModal from '@/components/CreateKnowledgeBaseModal.vue'
import AppButton from '@/components/ui/AppButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
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
const projectId = route.params.projectId as string

const kbs = ref<KnowledgeBase[]>([])
const loading = ref(true)
const sortMode = ref<SortMode>('custom')
const sortOpen = ref(false)
const createOpen = ref(false)

onMounted(async () => {
  kbs.value = await api.listProjectKnowledgeBases(projectId)
  loading.value = false
})

const displayed = computed(() => {
  const list = [...kbs.value]
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
      return list.sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0))
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
  const orderedIds = list.map((k) => k.id)
  await api.updateProjectKnowledgeBaseOrder(projectId, orderedIds)
  kbs.value = kbs.value.map((k) => ({ ...k, sortOrder: orderedIds.indexOf(k.id) + 1 }))
}

function selectSort(value: SortMode) {
  sortMode.value = value
  sortOpen.value = false
}

function clearDrag() {
  dragIndex.value = null
  dragOverIndex.value = null
}

function onCreated(kb: KnowledgeBase) {
  kbs.value.push(kb)
}

/** ---------------- 删除知识库 ---------------- */

const pendingDelete = ref<KnowledgeBase | null>(null)
const deletingKbId = ref<string | null>(null)

/** 删除确认 → 后端级联清理文件/策略/向量/任务并移出列表 */
async function confirmDelete() {
  const kb = pendingDelete.value
  if (!kb || deletingKbId.value) return
  deletingKbId.value = kb.id
  try {
    await deleteKnowledgeBase(kb.id)
    kbs.value = kbs.value.filter((k) => k.id !== kb.id)
    pendingDelete.value = null
  } finally {
    deletingKbId.value = null
  }
}
</script>

<template>
  <div class="lg:flex lg:h-full lg:min-h-0 lg:flex-col">
    <!-- 工具栏：排序 + 新建知识库 -->
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
      <AppButton variant="primary" class="ml-auto" @click="createOpen = true">
        <Plus class="size-4" />
        新建知识库
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

    <!-- 知识库卡片网格：桌面端仅列表区域滚动 -->
    <section
      v-else-if="displayed.length"
      v-scroll-auto-hide
      class="scroll-auto-hide grid grid-cols-1 gap-5 sm:grid-cols-2 lg:min-h-0 lg:flex-1 lg:auto-rows-max lg:grid-cols-3 lg:overflow-y-auto lg:pr-2 xl:grid-cols-4"
    >
      <RouterLink
        v-for="(kb, i) in displayed"
        :key="kb.id"
        :to="`/knowledge/${kb.id}`"
        v-spotlight
        :draggable="isCustom"
        class="card-surface spotlight group relative block overflow-hidden p-5 transition-all duration-300 ease-out hover:-translate-y-1 hover:border-white/10 hover:shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_12px_40px_rgba(0,0,0,0.5),0_0_60px_rgba(94,106,210,0.12)]"
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
      >
        <span class="absolute right-3 top-3 flex items-center gap-1">
          <GripVertical
            v-if="isCustom"
            class="size-4 cursor-grab text-muted opacity-0 transition-opacity group-hover:opacity-100"
          />
          <button
            type="button"
            class="flex size-7 items-center justify-center rounded-md text-muted opacity-0 transition-all duration-200 hover:bg-red-500/10 hover:text-red-500 focus-visible:opacity-100 group-hover:opacity-100"
            :class="{ 'pointer-events-none opacity-40': deletingKbId !== null && deletingKbId !== kb.id }"
            :aria-label="`删除知识库 ${kb.name}`"
            @click.stop.prevent="pendingDelete = kb"
          >
            <Trash2 class="size-4" :stroke-width="1.75" />
          </button>
        </span>
        <div class="flex items-center gap-3 pr-5">
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-accent/30 to-accent/5 text-accent"
          >
            <BookOpen class="size-5" :stroke-width="1.75" />
          </div>
          <h3 class="min-w-0 flex-1 truncate text-[15px] font-semibold tracking-tight">
            {{ kb.name }}
          </h3>
        </div>
        <p
          class="mt-4 line-clamp-2 min-h-10 text-sm leading-relaxed text-muted"
          :title="kb.description || undefined"
        >
          {{ kb.description || '暂无描述' }}
        </p>
        <div class="mt-4 flex items-center gap-4 border-t border-white/6 pt-4 text-xs text-muted">
          <span class="inline-flex items-center gap-1.5">
            <Files class="size-3.5" />
            {{ kb.fileCount }} 文档
          </span>
          <span v-if="kb.embedModel" class="inline-flex min-w-0 items-center gap-1.5">
            <Cpu class="size-3.5 shrink-0" />
            <span class="truncate" :title="kb.embedModel">{{ kb.embedModel }}</span>
          </span>
        </div>
      </RouterLink>
    </section>

    <!-- 空状态 -->
    <section v-else>
      <EmptyState
        title="还没有知识库"
        description="创建第一个项目知识库，沉淀项目文档。"
      >
        <template #icon><BookOpen class="size-6" :stroke-width="1.5" /></template>
        <template #action>
          <AppButton variant="primary" @click="createOpen = true">
            <Plus class="size-4" />
            新建知识库
          </AppButton>
        </template>
      </EmptyState>
    </section>

    <CreateKnowledgeBaseModal
      :open="createOpen"
      :project-id="projectId"
      @close="createOpen = false"
      @created="onCreated"
    />

    <ConfirmModal
      :open="!!pendingDelete"
      title="删除知识库"
      :description="`将删除「${pendingDelete?.name ?? ''}」及其全部文件、解析任务、MinIO 对象、向量分块等数据，不可恢复。确定删除吗？`"
      confirm-text="删除"
      danger
      :loading="deletingKbId === pendingDelete?.id"
      @close="pendingDelete = null"
      @confirm="confirmDelete"
    />
  </div>
</template>
