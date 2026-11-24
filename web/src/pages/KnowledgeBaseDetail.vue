<script setup lang="ts">
import { Clock, Download, Files, Layers, Trash2, Upload } from '@lucide/vue'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as api from '@/api/knowledge'
import type { KnowledgeBase, KnowledgeFile } from '@/types/knowledge'
import BackButton from '@/components/BackButton.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import KnowledgeStrategyPanel from '@/components/KnowledgeStrategyPanel.vue'
import GraphSchemaPanel from '@/components/GraphSchemaPanel.vue'
import AppBadge from '@/components/ui/AppBadge.vue'
import AppButton from '@/components/ui/AppButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import UploadModal from '@/components/UploadModal.vue'
import { formatBytes, formatDateTime } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const kbId = computed(() => route.params.kbId as string)

type DetailTab = 'files' | 'strategy' | 'schema'

const TABS: { value: DetailTab; label: string }[] = [
  { value: 'files', label: '文件列表' },
  { value: 'strategy', label: '文件处理策略' },
  { value: 'schema', label: '图谱schema' },
]

const activeTab = ref<DetailTab>('files')

/** 策略面板实例：文件列表点击策略名时定位到对应策略详情 */
const strategyPanelRef = ref<InstanceType<typeof KnowledgeStrategyPanel> | null>(null)
/** 图谱schema面板实例：切到该 Tab 时重新加载 */
const schemaPanelRef = ref<InstanceType<typeof GraphSchemaPanel> | null>(null)

/** 切到策略 Tab 并打开指定策略详情（面板内部会先刷新列表再定位） */
function openStrategyDetail(strategyId: string): void {
  activeTab.value = 'strategy'
  nextTick(() => strategyPanelRef.value?.openById(strategyId))
}

/** 每次进入「文件处理策略」Tab（点击切换或返回策略列表）时调接口重新加载列表 */
watch(activeTab, (tab) => {
  if (tab === 'strategy') void strategyPanelRef.value?.reload()
  if (tab === 'schema') void schemaPanelRef.value?.reload()
})

const kb = ref<KnowledgeBase | null>(null)
const files = ref<KnowledgeFile[]>([])
const loading = ref(true)
const uploadOpen = ref(false)
/** 所属团队 ID（知识库详情接口附带，用于返回项目页） */
const teamId = ref('')

// 文件解析由后端 worker 异步完成：存在处理中的文件时每 3 秒轮询刷新，
// 全部到终态（indexed/failed）后停止
let pollTimer: ReturnType<typeof setInterval> | undefined

onMounted(async () => {
  const [kbRes, fileList] = await Promise.all([
    api.getKnowledgeBase(kbId.value).catch(() => null),
    api.listFiles(kbId.value),
  ])
  kb.value = kbRes
  teamId.value = kbRes?.teamId ?? ''
  files.value = fileList
  loading.value = false
  syncKbStats()
  startPolling()
})

onUnmounted(stopPolling)

/** 用文件列表回填知识库统计 */
function syncKbStats() {
  if (!kb.value) return
  kb.value.fileCount = files.value.length
  kb.value.chunkCount = files.value.reduce((sum, f) => sum + f.chunkCount, 0)
}

function startPolling() {
  if (pollTimer || !files.value.some((f) => f.status === 'processing')) return
  pollTimer = setInterval(async () => {
    try {
      files.value = await api.listFiles(kbId.value)
      syncKbStats()
    } catch {
      // 轮询失败静默，下一轮重试
    }
    if (!files.value.some((f) => f.status === 'processing')) stopPolling()
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = undefined
  }
}

function onUploaded(created: KnowledgeFile[]) {
  files.value.unshift(...created)
  syncKbStats()
  startPolling()
}

/** 返回目标：项目知识库 → 所属项目页；个人知识库 → 首页 */
const backTarget = computed(() =>
  teamId.value && kb.value?.projectId
    ? `/team/${teamId.value}/project/${kb.value.projectId}/kbs`
    : '/',
)

const sortedFiles = computed(() => [...files.value].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)))

function openFile(file: KnowledgeFile) {
  // 处理中的文件尚未生成分块，不允许进入分块页
  if (file.status !== 'indexed') return
  router.push(`/knowledge/${kbId.value}/files/${file.id}`)
}

const downloadingId = ref<string | null>(null)

/** 下载文件原内容（后端流式返回 MinIO 对象） */
async function download(file: KnowledgeFile) {
  if (downloadingId.value) return
  downloadingId.value = file.id
  try {
    const blob = await api.downloadFile(file.id)
    saveBlob(blob, file.name)
  } finally {
    downloadingId.value = null
  }
}

/** ---------------- 删除文件 ---------------- */

const pendingDelete = ref<KnowledgeFile | null>(null)
const deletingFileId = ref<string | null>(null)

/** 删除确认 → 清理后端全部数据（任务/MinIO/向量/分块/记录）并移出列表 */
async function confirmDelete() {
  const file = pendingDelete.value
  if (!file || deletingFileId.value) return
  deletingFileId.value = file.id
  try {
    await api.deleteFile(file.id)
    files.value = files.value.filter((f) => f.id !== file.id)
    syncKbStats()
    pendingDelete.value = null
  } finally {
    deletingFileId.value = null
  }
}

/** 通过临时 objectURL 触发浏览器保存 */
function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>

<template>
  <div>
    <!-- 返回 + 标题区 -->
    <section class="pb-8 pt-6 md:pt-8">
      <BackButton :to="backTarget" />

      <div class="mt-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 class="text-gradient text-3xl font-semibold tracking-tight md:text-4xl">
            {{ kb?.name ?? '加载中…' }}
          </h1>
          <p v-if="kb?.description" class="mt-2 max-w-xl text-sm leading-relaxed text-muted">
            {{ kb.description }}
          </p>
          <div v-if="kb" class="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted">
            <span class="inline-flex items-center gap-1.5">
              <Files class="size-3.5" /> {{ kb.fileCount }} 文件
            </span>
            <span class="inline-flex items-center gap-1.5">
              <Layers class="size-3.5" /> {{ kb.chunkCount }} 分块
            </span>
            <span class="inline-flex items-center gap-1.5">
              <Clock class="size-3.5" /> 更新于 {{ formatDateTime(kb.updatedAt) }}
            </span>
          </div>
        </div>
        <AppButton v-if="activeTab === 'files'" variant="primary" @click="uploadOpen = true">
          <Upload class="size-4" />
          上传文件
        </AppButton>
      </div>
    </section>

    <!-- Tab 导航 -->
    <nav class="flex items-center gap-1 border-b border-white/6" role="tablist" aria-label="知识库详情">
      <button
        v-for="tab in TABS"
        :id="`kb-tab-${tab.value}`"
        :key="tab.value"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.value"
        :aria-controls="`kb-panel-${tab.value}`"
        class="relative px-3 py-2.5 text-sm transition-colors duration-200"
        :class="activeTab === tab.value ? 'font-medium text-ink' : 'text-muted hover:text-ink'"
        @click="activeTab = tab.value"
      >
        {{ tab.label }}
        <span
          v-if="activeTab === tab.value"
          class="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent"
        />
      </button>
    </nav>

    <!-- 文件列表 -->
    <section
      v-show="activeTab === 'files'"
      id="kb-panel-files"
      role="tabpanel"
      aria-labelledby="kb-tab-files"
      class="pt-7"
    >
      <section v-if="loading" class="card-surface animate-pulse p-2" aria-busy="true">
        <div v-for="i in 3" :key="i" class="flex items-center gap-4 px-4 py-4">
          <div class="size-9 rounded-lg bg-white/5" />
          <div class="h-3.5 w-1/3 rounded bg-white/5" />
        </div>
      </section>

      <section
        v-else-if="sortedFiles.length"
        class="overflow-hidden rounded-2xl border border-white/6 bg-gradient-to-b from-white/[0.04] to-white/[0.01]"
      >
        <!-- 表头 -->
        <div
          class="hidden border-b border-white/6 px-5 py-3 font-mono text-[11px] tracking-widest text-muted md:grid md:grid-cols-[minmax(0,1.5fr)_110px_90px_110px_130px_150px_96px] md:items-center md:gap-4"
        >
          <span>文件</span>
          <span>大小</span>
          <span>分块</span>
          <span>状态</span>
          <span>处理策略</span>
          <span class="text-right">更新时间</span>
          <span class="text-right">操作</span>
        </div>
        <div class="divide-y divide-white/6">
          <div
            v-for="file in sortedFiles"
            :key="file.id"
            role="button"
            tabindex="0"
            class="group grid w-full grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-4 px-5 py-4 text-left transition-colors duration-200 hover:bg-white/[0.04] md:grid-cols-[minmax(0,1.5fr)_110px_90px_110px_130px_150px_96px]"
            :class="{ 'cursor-default': file.status === 'processing' }"
            @click="openFile(file)"
            @keydown.enter.prevent="openFile(file)"
            @keydown.space.prevent="openFile(file)"
          >
            <span class="flex min-w-0 items-center gap-3">
              <span
                class="flex size-9 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03] text-accent"
              >
                <Files class="size-4" :stroke-width="1.75" />
              </span>
              <span class="min-w-0">
                <span class="block truncate text-sm font-medium">{{ file.name }}</span>
                <span class="block truncate font-mono text-[11px] text-muted md:hidden">
                  {{ formatBytes(file.size) }} · {{ file.chunkCount }} 分块 ·
                  {{ file.strategyName ?? '未指定策略' }} ·
                  {{ formatDateTime(file.updatedAt) }}
                </span>
              </span>
            </span>
            <span class="hidden font-mono text-xs text-muted md:block">{{ formatBytes(file.size) }}</span>
            <span class="hidden font-mono text-xs text-muted md:block">{{ file.chunkCount }}</span>
            <span>
              <AppBadge v-if="file.status === 'indexed'" tone="success">已索引</AppBadge>
              <AppBadge v-else-if="file.status === 'failed'" tone="danger" :title="file.error ?? ''">
                失败
              </AppBadge>
              <AppBadge v-else tone="accent">处理中</AppBadge>
            </span>
            <span class="hidden min-w-0 md:block">
              <button
                v-if="file.strategyId"
                type="button"
                class="max-w-full truncate rounded px-1 py-0.5 text-left text-xs text-accent underline-offset-2 transition-colors duration-200 hover:underline"
                :title="`查看策略「${file.strategyName}」详情`"
                @click.stop="openStrategyDetail(file.strategyId)"
              >
                {{ file.strategyName }}
              </button>
              <span v-else class="text-xs text-muted">未指定</span>
            </span>
            <span class="hidden text-right text-xs text-muted md:block">
              {{ formatDateTime(file.updatedAt) }}
            </span>
            <span class="flex items-center justify-end gap-1">
              <button
                type="button"
                class="flex size-7 items-center justify-center rounded-md text-muted transition-colors duration-200 hover:bg-white/8 hover:text-ink"
                :class="{ 'pointer-events-none opacity-40': downloadingId !== null && downloadingId !== file.id }"
                :aria-label="`下载 ${file.name}`"
                @click.stop="download(file)"
              >
                <Download class="size-4" :stroke-width="1.75" />
              </button>
              <button
                type="button"
                class="flex size-7 items-center justify-center rounded-md text-muted transition-colors duration-200 hover:bg-red-500/10 hover:text-red-500"
                :class="{ 'pointer-events-none opacity-40': deletingFileId !== null && deletingFileId !== file.id }"
                :aria-label="`删除 ${file.name}`"
                @click.stop="pendingDelete = file"
              >
                <Trash2 class="size-4" :stroke-width="1.75" />
              </button>
            </span>
          </div>
        </div>
      </section>

      <section v-else>
        <EmptyState
          title="还没有文件"
          description="上传文档后自动解析、分块并构建向量索引。"
        >
          <template #icon><Upload class="size-6" :stroke-width="1.5" /></template>
          <template #action>
            <AppButton variant="primary" @click="uploadOpen = true">
              <Upload class="size-4" />
              上传文件
            </AppButton>
          </template>
        </EmptyState>
      </section>
    </section>

    <!-- 文件处理策略 -->
    <section
      v-show="activeTab === 'strategy'"
      id="kb-panel-strategy"
      role="tabpanel"
      aria-labelledby="kb-tab-strategy"
      class="pt-7"
    >
      <KnowledgeStrategyPanel ref="strategyPanelRef" :kb-id="kbId" :project-id="kb?.projectId" />
    </section>

    <!-- 图谱schema -->
    <section
      v-show="activeTab === 'schema'"
      id="kb-panel-schema"
      role="tabpanel"
      aria-labelledby="kb-tab-schema"
      class="pt-7"
    >
      <GraphSchemaPanel ref="schemaPanelRef" :kb-id="kbId" />
    </section>

    <UploadModal :open="uploadOpen" :kb-id="kbId" @close="uploadOpen = false" @uploaded="onUploaded" />

    <ConfirmModal
      :open="!!pendingDelete"
      title="删除文件"
      :description="`将删除「${pendingDelete?.name ?? ''}」及其解析任务、MinIO 对象、向量分块等全部数据，不可恢复。确定删除吗？`"
      confirm-text="删除"
      danger
      :loading="deletingFileId === pendingDelete?.id"
      @close="pendingDelete = null"
      @confirm="confirmDelete"
    />
  </div>
</template>
