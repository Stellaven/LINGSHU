<script setup lang="ts">
import { ShieldAlert } from '@lucide/vue'
import { ref } from 'vue'
import * as api from '@/api/knowledge'
import type { FileParseStrategy } from '@/types/knowledge'
import AppButton from '@/components/ui/AppButton.vue'
import AppModal from '@/components/ui/AppModal.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import StrategyFormModal from '@/components/strategy/StrategyFormModal.vue'
import StrategyList from '@/components/strategy/StrategyList.vue'

const props = defineProps<{
  kbId: string
  /** 知识库所属项目 ID，用于策略表单拉取项目内嵌入模型 */
  projectId?: string
}>()

type BlockedAction = 'delete'

const loading = ref(true)
const strategies = ref<FileParseStrategy[]>([])

/** 修改/删除前校验文档引用关系时的加载状态 */
const checking = ref(false)
/** 通用操作错误（引用校验拦截等场景走 blocked 弹窗） */
const actionError = ref('')

/** 新建 / 修改表单（view = 被引用策略的只读详情） */
const formOpen = ref(false)
const formMode = ref<'create' | 'edit' | 'view'>('create')
const editingStrategy = ref<FileParseStrategy | null>(null)

/** 引用校验拦截提示 */
const blocked = ref<{ action: BlockedAction; strategy: FileParseStrategy } | null>(null)

/** 删除确认 */
const pendingDelete = ref<FileParseStrategy | null>(null)
const deleting = ref(false)

/**
 * 加载策略列表。由外层在进入「文件处理策略」Tab 时触发（含点击 Tab / 返回列表），
 * openById 等入口复用同一函数；并发调用共享同一次请求，避免重复拉取。
 */
let inflight: Promise<void> | null = null
function load(): Promise<void> {
  if (inflight) return inflight
  loading.value = true
  inflight = api
    .listParseStrategies(props.kbId)
    .then((data) => {
      strategies.value = data
    })
    .finally(() => {
      loading.value = false
      inflight = null
    })
  return inflight
}

/** 拉取最新策略并同步到列表（引用数由后端实时聚合） */
async function refreshStrategy(strategyId: string): Promise<FileParseStrategy> {
  const fresh = await api.getParseStrategy(props.kbId, strategyId)
  const index = strategies.value.findIndex((s) => s.id === fresh.id)
  if (index >= 0) strategies.value[index] = fresh
  else strategies.value.unshift(fresh)
  return fresh
}

/**
 * 打开策略编排器（查看详情与修改共用入口）：先刷新策略获取实时引用数——
 * 已被文件引用的策略以只读详情（view）展示；
 * 未被引用打开编辑表单。
 */
async function openOrchestrator(strategy: FileParseStrategy) {
  if (checking.value) return
  actionError.value = ''
  checking.value = true
  try {
    const fresh = await refreshStrategy(strategy.id)
    formMode.value = fresh.documentCount > 0 ? 'view' : 'edit'
    editingStrategy.value = fresh
    formOpen.value = true
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : '校验策略引用失败，请稍后重试'
  } finally {
    checking.value = false
  }
}

/**
 * 供外部（文件列表点击策略名）打开指定策略：
 * 先刷新列表保证引用数等数据最新，存在时打开编排器。
 */
async function openById(strategyId: string): Promise<void> {
  await load()
  const target = strategies.value.find((s) => s.id === strategyId)
  if (target) await openOrchestrator(target)
}

defineExpose({ openById, reload: load })

function openCreate() {
  actionError.value = ''
  formMode.value = 'create'
  editingStrategy.value = null
  formOpen.value = true
}

/**
 * 删除入口：先校验是否有文档引用；已引用则拦截并提示，
 * 未引用才弹出删除确认。
 */
async function requestDelete(strategy: FileParseStrategy) {
  if (checking.value) return
  actionError.value = ''
  checking.value = true
  try {
    const fresh = await refreshStrategy(strategy.id)
    if (fresh.documentCount > 0) {
      blocked.value = { action: 'delete', strategy: fresh }
      return
    }
    pendingDelete.value = fresh
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : '校验策略引用失败，请稍后重试'
  } finally {
    checking.value = false
  }
}

async function confirmDelete() {
  const strategy = pendingDelete.value
  if (!strategy || deleting.value) return
  deleting.value = true
  actionError.value = ''
  try {
    await api.deleteParseStrategy(props.kbId, strategy.id)
    strategies.value = strategies.value.filter((s) => s.id !== strategy.id)
    pendingDelete.value = null
  } catch (error) {
    pendingDelete.value = null
    actionError.value = error instanceof Error ? error.message : '删除策略失败，请稍后重试'
  } finally {
    deleting.value = false
  }
}

/** 表单保存成功后更新列表（新建置顶，修改原位替换） */
function onSaved(saved: FileParseStrategy) {
  const index = strategies.value.findIndex((s) => s.id === saved.id)
  if (index >= 0) strategies.value[index] = saved
  else strategies.value.unshift(saved)
}
</script>

<template>
  <div>
    <p
      v-if="actionError"
      class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2.5 text-xs leading-relaxed text-red-300"
      role="alert"
    >
      {{ actionError }}
    </p>

    <StrategyList
      :strategies="strategies"
      :loading="loading"
      @create="openCreate"
      @open="openOrchestrator"
      @edit="openOrchestrator"
      @delete="requestDelete"
    />

    <StrategyFormModal
      :open="formOpen"
      :kb-id="props.kbId"
      :project-id="props.projectId"
      :mode="formMode"
      :strategy="editingStrategy"
      @close="formOpen = false"
      @saved="onSaved"
    />

    <!-- 文档引用校验拦截：已引用的策略不可删除 -->
    <AppModal :open="!!blocked" title="无法删除策略" width="max-w-md" @close="blocked = null">
      <div class="flex items-start gap-3">
        <span
          class="flex size-9 shrink-0 items-center justify-center rounded-lg border border-amber-400/20 bg-amber-400/10 text-amber-300"
        >
          <ShieldAlert class="size-4" :stroke-width="1.75" />
        </span>
        <div class="min-w-0 space-y-2 text-sm leading-relaxed text-muted">
          <p>
            策略
            <span class="font-medium text-ink">“{{ blocked?.strategy.name }}”</span>
            已被
            <span class="font-medium text-ink">{{ blocked?.strategy.documentCount }}</span>
            个文档引用，暂时不能删除。
          </p>
          <p class="text-xs">
            请先在文件列表中调整这些文档使用的处理策略（或删除相关文档），再重试。
          </p>
        </div>
      </div>

      <template #footer>
        <AppButton variant="primary" @click="blocked = null">我知道了</AppButton>
      </template>
    </AppModal>

    <ConfirmModal
      :open="!!pendingDelete"
      title="删除策略"
      :description="`删除后策略配置不可恢复，确定删除“${pendingDelete?.name ?? ''}”吗？`"
      confirm-text="删除"
      danger
      :loading="deleting"
      @close="pendingDelete = null"
      @confirm="confirmDelete"
    />
  </div>
</template>
