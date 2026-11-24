<script setup lang="ts">
/**
 * 新建/修改/查看文件处理策略 —— 处理策略编排器
 * ------------------------------------------------------------------
 * 三栏工作台（布局与操作逻辑复刻设计原型 rag-strategy-orchestrator.html）：
 *   左：组件库（搜索 / 分组 / 点击 + 或拖入；只读查看模式隐藏）
 *   中：编排画布（四条泳道：解析 → 文档级提取 → 分块 → 块级提取，
 *       同泳道拖拽排序、提取器 ⇅ 切换作用域、逐实例 LLM、参数展开、校验告警、撤销）
 *   右：执行顺序镜像（唯一真相源）
 * mode=view 为只读详情（已被文件引用的策略）：无组件库与操作控件，仅展示编排。
 * 保存时提交完整 stages 编排序列。
 */
import { AlertCircle, Boxes, Plus, RotateCcw, Search } from '@lucide/vue'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import * as api from '@/api/knowledge'
import * as modelsApi from '@/api/models'
import type {
  ChunkStrategy,
  FileParseStrategy,
  FileParseStrategyPatch,
  FileParser,
  GraphSchema,
  StageExtractorEntry,
  StrategyStages,
} from '@/types/knowledge'
import type { ChatModelOption } from '@/types/models'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppModal from '@/components/ui/AppModal.vue'
import AppSwitch from '@/components/ui/AppSwitch.vue'
import {
  ORCHESTRATOR_COMPONENTS,
  ORCHESTRATOR_LANES,
  ORCHESTRATOR_TYPE_META,
  DEFAULT_STAGES,
  CHUNKER_PARAM_FIELDS,
  EXTRACTOR_PARAM_FIELDS,
  flattenStages,
  normalizeSplitEntries,
} from './options'
import type { OrchestratorComponent, OrchestratorLane, OrchestratorType } from './options'
import StrategyStageNode from './StrategyStageNode.vue'

type LaneKey = OrchestratorLane['key']

const props = defineProps<{
  open: boolean
  kbId: string
  /** 所属项目 ID：用于拉取项目内配置的嵌入/LLM 模型 */
  projectId?: string
  mode: 'create' | 'edit' | 'view'
  strategy?: FileParseStrategy | null
}>()

const emit = defineEmits<{
  close: []
  saved: [strategy: FileParseStrategy]
}>()

/** 只读详情模式（已被文件引用的策略）：无组件库，字段与编排仅展示 */
const readonly = computed(() => props.mode === 'view')

/** ---------------- 编排状态 ---------------- */
const strategyName = ref('')
const graph = ref(true)
/**
 * 知识库图谱schema（「图谱schema」页签维护，策略内只读）：graph=true 时要求已创建，
 * 开启构建图谱的策略按此 schema 对齐抽取，展示但不可修改。
 */
const kbSchema = ref<GraphSchema | null>(null)
const loadingSchema = ref(false)
const stages = reactive<StrategyStages>({ parser: [], pre_extract: [], split: [], post_extract: [] })
/** 参数展开面板（key: laneKey:idx） */
const openParams = ref<Record<string, boolean>>({})
/** 撤销栈：仅编排序列快照（名称/图谱不参与） */
const undoStack = ref<string[]>([])

/** 拖拽上下文：组件库拖入（from=lib）或泳道内排序（from=lane） */
interface DragCtx {
  from: 'lib' | 'lane'
  type?: OrchestratorType
  id?: string
  lane?: LaneKey
  idx?: number
}
const dragCtx = ref<DragCtx | null>(null)
/** 节点间插入线标记（drop-before/after） */
const dropMark = ref<{ lane: LaneKey; idx: number; after: boolean } | null>(null)
/** 泳道高亮 */
const laneHover = ref<LaneKey | null>(null)
/** 拖拽中的节点（半透明） */
const draggingKey = ref<string | null>(null)

/** ---------------- 消息提示 ---------------- */
const toastMessage = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined
function toast(msg: string) {
  toastMessage.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toastMessage.value = ''), 2200)
}

/** ---------------- 模型选项 ---------------- */
/** 知识库绑定的嵌入模型（固定不可修改，保存时随策略写入） */
const kbEmbedModel = ref('')
const kbEmbedInstance = ref('')
const embedModelDisplay = computed(() => {
  if (!kbEmbedModel.value) return '知识库未配置嵌入模型'
  return kbEmbedInstance.value
    ? `${kbEmbedModel.value}（来自实例「${kbEmbedInstance.value}」）`
    : kbEmbedModel.value
})

async function loadEmbeddingInfo() {
  try {
    const [kb, models] = await Promise.all([
      api.getKnowledgeBase(props.kbId),
      props.projectId ? modelsApi.listEmbeddingModels(props.projectId) : Promise.resolve([]),
    ])
    kbEmbedModel.value = kb.embedModel ?? ''
    kbEmbedInstance.value = models.find((model) => model.name === kb.embedModel)?.instanceName ?? ''
  } catch {
    kbEmbedModel.value = ''
    kbEmbedInstance.value = ''
  }
}

/** 项目内 chat 模型（后端接口查询）：每个提取器实例独立选择执行 LLM（空串 = 不使用，提取跳过） */
const chatModels = ref<ChatModelOption[]>([])
const loadingChat = ref(false)
const chatModelOptions = computed(() => [
  { value: '', label: '不使用' },
  ...chatModels.value.map((model) => ({ value: model.name, label: model.name })),
])
const defaultLlm = computed(() => chatModels.value[0]?.name ?? '')

async function loadChatModels() {
  if (!props.projectId || loadingChat.value) return
  loadingChat.value = true
  try {
    chatModels.value = await modelsApi.listChatModels(props.projectId)
  } catch {
    chatModels.value = []
  } finally {
    loadingChat.value = false
  }
}

/** ---------------- 打开时水合 ---------------- */
onBeforeUnmount(() => document.removeEventListener('keydown', onUndoKeydown))

/** ---------------- 扁平序列与组件目录 ---------------- */
const query = ref('')
/** 组件库分组（按搜索词过滤） */
const librarySections = computed(() => {
  const q = query.value.trim().toLowerCase()
  return (['parser', 'splitter', 'extractor'] as OrchestratorType[])
    .map((type) => ({
      type,
      meta: ORCHESTRATOR_TYPE_META[type],
      components: ORCHESTRATOR_COMPONENTS[type].filter(
        (c) => !q || `${c.name}${c.description}`.toLowerCase().includes(q),
      ),
    }))
    .filter((section) => section.components.length > 0)
})

/** 提取器泳道条目（pre/post） */
function laneEntries(lane: OrchestratorLane): StageExtractorEntry[] {
  return lane.key === 'pre' ? stages.pre_extract : stages.post_extract
}
/** 解析器/分块器泳道组件条目（统一为 {id, params}，解析器无参数配置） */
function laneComponentEntries(lane: OrchestratorLane): {
  id: string
  params: Record<string, number | string>
}[] {
  if (lane.type === 'parser') return stages.parser.map((id) => ({ id, params: {} }))
  return normalizeSplitEntries(stages.split)
}
/** 提取器泳道作用域 */
function extractorScope(lane: OrchestratorLane): 'pre' | 'post' {
  return lane.key === 'pre' ? 'pre' : 'post'
}

function findComponent(type: OrchestratorType, id: string): OrchestratorComponent {
  return ORCHESTRATOR_COMPONENTS[type].find((c) => c.id === id)!
}

/** 扁平执行序列（顺序即 transformations 顺序） */
const flat = computed(() => flattenStages(stages))
const usedIds = computed(() => flat.value.map((step) => step.component.id))
/** laneKey:idx → 全局序号 */
const seqMap = computed(() => {
  const map = new Map<string, number>()
  flat.value.forEach((step) => map.set(`${step.lane}:${step.idx}`, step.seq))
  return map
})

/** 镜像面板元信息行 */
function stepMeta(lane: LaneKey, idx: number): string {
  if (lane === 'parser') return '输入 Document'
  if (lane === 'split') return idx > 0 ? `第 ${idx + 1} 级级联` : '分块'
  if (lane === 'pre') return '文档级 · 分块前'
  return '块级 · 分块后'
}

/** ---------------- 编排操作 ---------------- */
function laneArray(lane: LaneKey): unknown[] {
  if (lane === 'parser') return stages.parser
  if (lane === 'pre') return stages.pre_extract
  if (lane === 'split') return stages.split
  return stages.post_extract
}

function laneDef(key: LaneKey): OrchestratorLane {
  return ORCHESTRATOR_LANES.find((l) => l.key === key)!
}

function snapshot() {
  undoStack.value.push(JSON.stringify({ ...stages }))
  if (undoStack.value.length > 40) undoStack.value.shift()
}
function mutate(fn: () => void) {
  snapshot()
  fn()
}
function onUndoKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') {
    e.preventDefault()
    const snap = undoStack.value.pop()
    if (!snap) return
    Object.assign(stages, JSON.parse(snap))
    toast('已撤销')
  }
}

function mkEntry(id: string): StageExtractorEntry {
  return { id: id as StageExtractorEntry['id'], llm: defaultLlm.value, params: {} }
}

function addComponent(type: OrchestratorType, id: string, laneKey?: LaneKey) {
  if (usedIds.value.includes(id)) {
    toast('该组件已在流程中')
    return
  }
  const lane = laneKey ?? (type === 'parser' ? 'parser' : type === 'splitter' ? 'split' : 'post')
  const def = laneDef(lane)
  if (def.type !== type) {
    toast('组件类型与该阶段不匹配')
    return
  }
  mutate(() => {
    if (lane === 'parser') stages.parser = [id as FileParser]
    else if (lane === 'split') stages.split.push({ id: id as ChunkStrategy, params: {} })
    else if (lane === 'pre') stages.pre_extract.push(mkEntry(id))
    else stages.post_extract.push(mkEntry(id))
  })
  toast(`已加入「${def.name}」末尾 · 序号 ${flat.value.length}`)
}

function removeEntry(lane: LaneKey, idx: number) {
  mutate(() => laneArray(lane).splice(idx, 1))
  delete openParams.value[`${lane}:${idx}`]
}

function moveWithin(lane: LaneKey, from: number, to: number) {
  if (from === to) return
  mutate(() => {
    const arr = laneArray(lane)
    const [x] = arr.splice(from, 1)
    arr.splice(to, 0, x)
  })
}

function shift(lane: LaneKey, idx: number, delta: number) {
  const arr = laneArray(lane)
  const to = idx + delta
  if (to < 0 || to >= arr.length) return
  moveWithin(lane, idx, to)
}

/** 提取器作用域切换：文档级(pre) ⇅ 块级(post) */
function switchScope(lane: LaneKey, idx: number) {
  const to = lane === 'pre' ? 'post' : 'pre'
  mutate(() => {
    const from = lane === 'pre' ? stages.pre_extract : stages.post_extract
    const [entry] = from.splice(idx, 1)
    ;(to === 'pre' ? stages.pre_extract : stages.post_extract).push(entry)
  })
  toast(to === 'pre' ? '已切换为文档级：分块前执行，每文档 1 次调用' : '已切换为块级：分块后执行，每块 1 次调用')
}

function setEntryLlm(lane: LaneKey, idx: number, llm: string) {
  const arr = lane === 'pre' ? stages.pre_extract : stages.post_extract
  if (!arr[idx]) return
  mutate(() => ((arr[idx] as StageExtractorEntry).llm = llm))
}

/** 分块器/提取器参数修改：清空（空串）即删除该键，按默认值生效 */
function setParam(lane: LaneKey, idx: number, key: string, value: number | string) {
  const arr = lane === 'pre' ? stages.pre_extract : lane === 'post' ? stages.post_extract : stages.split
  const entry = arr[idx]
  if (!entry) return
  mutate(() => {
    if (value === '' || value === undefined) delete entry.params[key]
    else entry.params[key] = value
  })
}

function toggleParams(key: string) {
  openParams.value[key] = !openParams.value[key]
}

function resetDragState() {
  dragCtx.value = null
  dropMark.value = null
  laneHover.value = null
  draggingKey.value = null
}

/** ---------------- 拖拽：组件库 → 泳道 / 泳道内排序 ---------------- */
function onLibDragStart(e: DragEvent, type: OrchestratorType, id: string) {
  dragCtx.value = { from: 'lib', type, id }
  e.dataTransfer?.setData('text/plain', 'lib')
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'
}
function onNodeDragStart(e: DragEvent, lane: LaneKey, idx: number, id: string) {
  if ((e.target as HTMLElement).closest?.('.llm-inline')) {
    e.preventDefault()
    return
  }
  dragCtx.value = { from: 'lane', lane, idx, id }
  e.dataTransfer?.setData('text/plain', 'node')
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
  draggingKey.value = `${lane}:${idx}`
}
function onDragEnd() {
  resetDragState()
}

function dragCompatible(lane: LaneKey): boolean {
  if (!dragCtx.value) return false
  const def = laneDef(lane)
  return dragCtx.value.from === 'lib'
    ? dragCtx.value.type === def.type
    : dragCtx.value.lane === lane
}

function onNodeDragOver(e: DragEvent, lane: LaneKey, idx: number) {
  if (!dragCompatible(lane)) return
  e.preventDefault()
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const after = e.clientY > rect.top + rect.height / 2
  dropMark.value = { lane, idx, after }
}

function onNodeDrop(e: DragEvent, lane: LaneKey, idx: number) {
  if (!dragCompatible(lane)) return
  e.preventDefault()
  e.stopPropagation()
  const ctx = dragCtx.value
  const mark = dropMark.value
  resetDragState()
  if (!ctx) return
  if (ctx.from === 'lib') {
    addComponent(ctx.type!, ctx.id!, lane)
  } else if (ctx.lane === lane) {
    let to = idx + (mark?.after ? 1 : 0)
    if (ctx.idx! < to) to--
    moveWithin(lane, ctx.idx!, to)
  }
}

function onLaneDragOver(e: DragEvent, lane: LaneKey) {
  if (!dragCompatible(lane)) return
  e.preventDefault()
  laneHover.value = lane
}

function onLaneDragLeave(e: DragEvent, lane: LaneKey) {
  const related = e.relatedTarget as HTMLElement | null
  if (!(e.currentTarget as HTMLElement).contains(related) && laneHover.value === lane) {
    laneHover.value = null
  }
}

function onLaneDrop(e: DragEvent, lane: LaneKey) {
  if (!dragCompatible(lane)) return
  e.preventDefault()
  const ctx = dragCtx.value
  resetDragState()
  if (!ctx) return
  if (ctx.from === 'lib') {
    addComponent(ctx.type!, ctx.id!, lane)
  } else if (ctx.lane === lane) {
    moveWithin(lane, ctx.idx!, laneArray(lane).length - 1)
  } else {
    toast('仅支持同类阶段内排序；提取器请用 ⇅ 切换作用域')
  }
}

/** ---------------- 校验告警 ---------------- */
interface AlertItem {
  level: 'error' | 'warn' | 'info'
  icon: string
  text: string
}
const alerts = computed<AlertItem[]>(() => {
  const out: AlertItem[] = []
  if (!stages.parser.length) {
    out.push({ level: 'error', icon: '⚠', text: '缺少解析器：处理流程至少需要一个解析步骤，策略无法保存。' })
  }
  if (!stages.split.length) {
    out.push({ level: 'error', icon: '⚠', text: '缺少分块器：请至少添加一个分块器。' })
  }
  if (stages.pre_extract.length && !stages.post_extract.length) {
    out.push({
      level: 'info',
      icon: '✓',
      text: '文档级提取：在分块前执行，每文档 1 次调用，生成的元数据会继承到所有块，成本可控。',
    })
  }
  const splitIds = stages.split.map((entry) => entry.id)
  const hasMd = splitIds.includes('markdown')
  const hasHtml = splitIds.includes('html')
  if (hasMd && hasHtml) {
    out.push({
      level: 'error',
      icon: '⚠',
      text: '结构分块冲突：Markdown 分块与 HTML 分块面向不同文档结构，不建议同时启用。请按文件类型拆分策略。',
    })
  }
  const swIdx = splitIds.indexOf('sentence_window')
  if (swIdx >= 0 && swIdx < splitIds.length - 1) {
    out.push({
      level: 'warn',
      icon: '!',
      text: `顺序提示：「句子窗口」通常作为最后一级切分器（其窗口元数据依赖最终节点边界），当前位于第 ${
        swIdx + 1
      } 级且后面还有切分器，请确认或用 ↓ 移至末级。`,
    })
  }
  // 分块参数合理性：重叠不小于块大小时后端会钳制到块大小-1，提前提示
  stages.split.forEach((entry, idx) => {
    const size = Number(entry.params.chunk_size)
    const overlap = Number(entry.params.chunk_overlap)
    if (
      Number.isFinite(size) &&
      Number.isFinite(overlap) &&
      size > 0 &&
      overlap >= size &&
      (entry.id === 'sentence' || entry.id === 'token')
    ) {
      out.push({
        level: 'warn',
        icon: '!',
        text: `第 ${idx + 1} 级「${findComponent('splitter', entry.id).name}」的重叠（${overlap}）不小于块大小（${size}），生效时将被钳制为块大小-1。`,
      })
    }
    if (entry.id === 'hierarchical' && typeof entry.params.chunk_sizes === 'string') {
      const sizes = entry.params.chunk_sizes
        .split(',')
        .map((s) => Number(s.trim()))
        .filter((s) => Number.isFinite(s) && s > 0)
      if (sizes.length >= 2 && sizes.some((s, i) => i > 0 && s >= sizes[i - 1])) {
        out.push({
          level: 'warn',
          icon: '!',
          text: `第 ${idx + 1} 级「层级分块」的层级块长应逐级递减，当前配置不满足，保存后将回退默认 1024/512/256。`,
        })
      }
    }
  })
  const llmLess = [...stages.pre_extract, ...stages.post_extract].filter((e) => !e.llm).length
  if (llmLess) {
    out.push({
      level: 'warn',
      icon: '!',
      text: `未选择 LLM：${llmLess} 个提取器实例未配置执行 LLM，解析时将自动跳过这些提取器。`,
    })
  }
  // 图谱schema校验：开启构建图谱须先在「图谱schema」页签创建schema
  if (graph.value && !loadingSchema.value && !kbSchema.value) {
    out.push({
      level: 'error',
      icon: '⚠',
      text: '尚未创建图谱schema：策略无法保存，请先在「图谱schema」页签定义实体与关系类型。',
    })
  }
  return out
})

/** ---------------- 图谱schema（知识库维度，只读展示） ---------------- */
async function loadGraphSchema() {
  if (loadingSchema.value) return
  loadingSchema.value = true
  try {
    kbSchema.value = await api.getGraphSchema(props.kbId)
  } catch {
    kbSchema.value = null
  } finally {
    loadingSchema.value = false
  }
}

/** ---------------- 打开时水合（置于全部状态声明之后） ---------------- */
watch(
  () => props.open,
  (open) => {
    if (open) {
      errorMessage.value = ''
      undoStack.value = []
      openParams.value = {}
      resetDragState()
      if ((props.mode === 'edit' || props.mode === 'view') && props.strategy) {
        strategyName.value = props.strategy.name
        graph.value = props.strategy.graph
        // props.strategy 是 reactive 代理，structuredClone 无法克隆，用 JSON 深拷贝；
        // split 条目归一化（兼容历史数据中的纯字符串 id），提取器条目补齐 params（历史数据无该键）
        Object.assign(stages, JSON.parse(JSON.stringify(props.strategy.stages)))
        stages.split = normalizeSplitEntries(stages.split)
        for (const entry of [...stages.pre_extract, ...stages.post_extract]) {
          if (!entry.params) entry.params = {}
        }
      } else {
        strategyName.value = ''
        graph.value = true
        Object.assign(stages, structuredClone(DEFAULT_STAGES))
      }
      // 图谱schema为知识库维度配置：无论模式均拉取展示（graph=true 时校验与展示）
      void loadGraphSchema()
      if (props.mode === 'view') {
        // 只读详情：嵌入模型直接展示策略保存值，无需拉取模型选项
        kbEmbedModel.value = props.strategy?.embedModel ?? ''
        kbEmbedInstance.value = ''
      } else {
        kbEmbedModel.value = ''
        kbEmbedInstance.value = ''
        void loadEmbeddingInfo()
        void loadChatModels()
        document.addEventListener('keydown', onUndoKeydown)
      }
    } else {
      document.removeEventListener('keydown', onUndoKeydown)
    }
  },
  { immediate: true },
)

/** ---------------- 保存 ---------------- */
const submitting = ref(false)
const errorMessage = ref('')

function resetAll() {
  snapshot()
  stages.parser = []
  stages.pre_extract = []
  stages.split = []
  stages.post_extract = []
  openParams.value = {}
  strategyName.value = ''
  toast('已清空所有配置')
}

async function onSubmit() {
  const name = strategyName.value.trim()
  if (!name) {
    toast('请先填写策略名称')
    return
  }
  if (!kbEmbedModel.value) {
    toast('当前知识库未配置嵌入模型，无法保存')
    return
  }
  const errs: string[] = []
  if (!stages.parser.length) errs.push('缺少解析器')
  if (!stages.split.length) errs.push('缺少分块器')
  if (errs.length) {
    toast(`保存失败：${errs.join('、')}`)
    return
  }
  // 图谱schema校验：开启构建图谱时知识库必须已创建schema（schema本身只读，在「图谱schema」页签维护）
  if (graph.value && !kbSchema.value) {
    toast('开启构建图谱前请先在「图谱schema」页签创建图谱schema')
    return
  }
  if (submitting.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    const patch: FileParseStrategyPatch = {
      name,
      embedModel: kbEmbedModel.value,
      graph: graph.value,
      stages: JSON.parse(JSON.stringify(stages)) as StrategyStages,
    }
    const saved =
      props.mode === 'edit' && props.strategy
        ? await api.updateParseStrategy(props.kbId, props.strategy.id, patch)
        : await api.createParseStrategy(props.kbId, patch)
    emit('saved', saved)
    emit('close')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal
    :open="props.open"
    :title="props.mode === 'edit' ? '修改策略' : props.mode === 'view' ? '策略详情' : '新建策略'"
    width="max-w-[1500px]"
    @close="emit('close')"
  >
    <div
      class="grid h-[72vh] min-h-[520px] grid-cols-1 overflow-y-auto md:overflow-hidden"
      :class="
        readonly
          ? 'md:grid-cols-[minmax(0,1fr)_270px] xl:grid-cols-[minmax(0,1fr)_290px]'
          : 'md:grid-cols-[250px_minmax(0,1fr)_270px] xl:grid-cols-[280px_minmax(0,1fr)_290px]'
      "
    >
      <!-- ============ 组件库（只读详情模式隐藏） ============ -->
      <aside v-if="!readonly" class="flex min-h-0 flex-col border-white/8 max-md:border-b md:border-r">
        <div class="px-4 pb-2 pt-4">
          <p class="text-xs font-semibold tracking-wide text-muted">组件库</p>
          <p class="mt-1.5 text-[11px] leading-relaxed text-muted/80">
            点击 + 或拖入右侧对应阶段。<br />同类组件可拖拽调整执行顺序。
          </p>
        </div>
        <div class="relative mx-4 mb-2">
          <Search class="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted/60" />
          <input
            v-model="query"
            placeholder="搜索组件…"
            class="w-full rounded-lg border border-white/10 bg-input py-2 pl-8 pr-3 text-xs text-ink outline-none transition-colors duration-200 placeholder:text-muted/60 focus:border-accent/50"
          />
        </div>
        <div class="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 pb-5">
          <div
            v-for="section in librarySections"
            :key="section.type"
            class="relative rounded-xl border px-2.5 pb-1.5 pt-2"
            :class="section.meta.border"
            :style="{ boxShadow: `inset 3px 0 0 0 ${section.meta.bar}` }"
          >
            <div class="flex items-center gap-1.5 px-1 pb-1.5 text-[11px] font-semibold text-muted">
              <span class="size-1.5 rounded-full" :class="section.meta.dot" />
              {{ section.meta.label }}
              <span class="ml-auto font-normal">{{ section.components.length }}</span>
            </div>
            <div
              v-for="component in section.components"
              :key="component.id"
              class="mb-1.5 flex items-center gap-2 rounded-lg border border-white/6 bg-white/[0.02] px-2.5 py-2 transition-all duration-200"
              :class="
                usedIds.includes(component.id)
                  ? 'cursor-default opacity-40'
                  : 'cursor-grab hover:translate-x-0.5 hover:border-accent/45 hover:bg-white/[0.05] active:cursor-grabbing'
              "
              :draggable="!usedIds.includes(component.id)"
              @dragstart="onLibDragStart($event, section.type, component.id)"
              @dragend="onDragEnd"
            >
              <span
                class="grid size-[26px] shrink-0 place-items-center rounded-md border border-white/8 bg-white/[0.04] text-ink/80"
              >
                <component :is="component.icon" class="size-3.5" :stroke-width="1.75" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-xs font-semibold">{{ component.name }}</span>
                <span class="mt-0.5 block truncate text-[10.5px] leading-snug text-muted/80">
                  {{ component.description }}
                </span>
              </span>
              <span v-if="usedIds.includes(component.id)" class="shrink-0 text-[10px] text-muted/70">已添加</span>
              <button
                v-else
                type="button"
                class="grid size-5 shrink-0 place-items-center rounded-md border border-white/10 text-muted transition-colors duration-200 hover:border-accent hover:bg-accent hover:text-white"
                :aria-label="`添加 ${component.name}`"
                @click.stop="addComponent(section.type, component.id)"
              >
                <Plus class="size-3" />
              </button>
            </div>
          </div>
          <p
            v-if="!librarySections.length"
            class="rounded-lg border border-dashed border-white/10 px-3 py-4 text-center text-[11px] text-muted"
          >
            没有匹配的组件
          </p>
        </div>
      </aside>

      <!-- ============ 编排画布 ============ -->
      <main
        class="min-h-0 overflow-y-auto bg-[radial-gradient(700px_320px_at_50%_-60px,rgba(94,106,210,0.09),transparent_70%)]"
      >
        <div class="mx-auto w-full max-w-[860px] px-6 py-5 md:px-8">
          <div class="mb-5 flex max-w-[420px] flex-col gap-3.5">
            <div class="space-y-2">
              <label for="strategy-name" class="text-sm font-semibold">
                策略名称 <span class="text-red-400">*</span>
              </label>
              <AppInput
                id="strategy-name"
                v-model="strategyName"
                placeholder="例如：默认文档策略"
                autocomplete="off"
                :disabled="readonly"
              />
            </div>
            <div class="space-y-2">
              <label for="strategy-embed" class="text-sm font-semibold">嵌入模型</label>
              <input
                id="strategy-embed"
                :value="embedModelDisplay"
                readonly
                :disabled="!kbEmbedModel"
                title="嵌入模型跟随知识库配置，不可修改"
                class="w-full cursor-default rounded-lg border border-white/10 bg-input px-3 py-2 text-[13px] outline-none disabled:text-muted"
                :class="kbEmbedModel ? 'text-ink' : 'text-muted/70'"
              />
            </div>
            <div class="space-y-2">
              <span class="text-sm font-semibold">构建知识图谱</span>
              <div class="flex items-center gap-2.5">
                <AppSwitch v-model="graph" :disabled="readonly" />
                <span class="font-mono text-[11px]" :class="graph ? 'text-accent' : 'text-muted'">
                  {{ graph ? '已开启' : '已关闭' }}
                </span>
                <span class="text-[10.5px] text-muted/80">开启须已创建知识库图谱schema</span>
              </div>
            </div>
            <!-- 图谱schema（graph 开启时展示，知识库维度配置，此处只读） -->
            <div v-if="graph" class="space-y-2">
              <div class="flex items-baseline justify-between gap-2">
                <span class="text-sm font-semibold">图谱schema</span>
                <span class="font-mono text-[11px] text-muted">知识库维度 · 在「图谱schema」页签维护</span>
              </div>
              <!-- 未创建 schema：阻断保存 -->
              <div
                v-if="!loadingSchema && !kbSchema"
                class="rounded-xl border border-amber-400/25 bg-amber-400/[0.06] px-3 py-2.5 text-[11px] leading-relaxed text-amber-200/90"
              >
                尚未创建图谱schema：请先在知识库详情的「图谱schema」页签定义实体与关系类型，再开启构建知识图谱。
              </div>
              <!-- 已创建 schema：只读展示实体/关系 -->
              <div v-else class="space-y-3 rounded-xl border border-white/10 bg-white/[0.015] p-3">
                <!-- 实体类型 -->
                <div class="space-y-1.5">
                  <p class="font-mono text-[11px] text-muted">
                    实体类型
                    <span class="ml-1 text-muted/70">{{ kbSchema?.entities.length ?? 0 }}</span>
                  </p>
                  <div
                    v-for="entity in kbSchema?.entities ?? []"
                    :key="entity.name"
                    class="rounded-lg border border-white/8 bg-white/[0.03] px-2.5 py-2"
                  >
                    <span class="font-mono text-[11.5px] font-semibold text-indigo-300">{{ entity.name }}</span>
                    <span v-if="entity.desc" class="ml-2 text-[11px] text-muted">{{ entity.desc }}</span>
                    <span
                      v-if="Object.keys(entity.properties).length"
                      class="mt-1 flex flex-wrap gap-1"
                    >
                      <span
                        v-for="(propDesc, propName) in entity.properties"
                        :key="propName"
                        class="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[10px] text-ink/75"
                        :title="propDesc"
                      >
                        {{ propName }}
                      </span>
                    </span>
                  </div>
                  <p
                    v-if="!kbSchema?.entities.length"
                    class="text-[11px] leading-relaxed text-muted/80"
                  >
                    schema 未定义实体类型。
                  </p>
                </div>
                <!-- 关系类型 -->
                <div class="space-y-1.5">
                  <p class="font-mono text-[11px] text-muted">
                    关系类型
                    <span class="ml-1 text-muted/70">{{ kbSchema?.relations.length ?? 0 }}</span>
                  </p>
                  <div
                    v-for="relation in kbSchema?.relations ?? []"
                    :key="relation.name"
                    class="flex items-center gap-2"
                  >
                    <span class="min-w-0 flex-1 truncate text-[11.5px] font-semibold text-ink/85">
                      {{ relation.name }}
                    </span>
                    <span class="shrink-0 font-mono text-[11px] text-muted">
                      {{ relation.subjectType || '?' }} → {{ relation.objectType || '?' }}
                    </span>
                  </div>
                  <p
                    v-if="!kbSchema?.relations.length"
                    class="text-[11px] leading-relaxed text-muted/80"
                  >
                    schema 未定义关系类型，构图时不约束关系。
                  </p>
                </div>
                <p class="flex items-center gap-1.5 text-[10.5px] leading-relaxed text-muted/80">
                  <Boxes class="size-3 shrink-0" :stroke-width="1.75" />
                  图谱schema为知识库维度配置，此处仅展示不可修改；如需调整请前往「图谱schema」页签。
                </p>
              </div>
            </div>
          </div>

          <div class="mb-4 flex items-center gap-2.5">
            <h4 class="m-0 text-sm font-semibold">执行流程编排</h4>
            <span class="rounded-full border border-accent/45 bg-accent/10 px-2.5 py-1 text-[11px] text-indigo-300">
              {{ flat.length }} 个步骤 · 严格有序
            </span>
          </div>

          <div>
            <template v-for="(lane, laneIdx) in ORCHESTRATOR_LANES" :key="lane.key">
              <div>
                <div class="mb-2 flex items-center gap-2">
                  <span
                    class="grid size-[21px] place-items-center rounded-md border text-[10.5px] font-bold"
                    :class="[
                      ORCHESTRATOR_TYPE_META[lane.type].border,
                      ORCHESTRATOR_TYPE_META[lane.type].bg,
                      ORCHESTRATOR_TYPE_META[lane.type].text,
                    ]"
                  >
                    {{ lane.idx }}
                  </span>
                  <span class="text-[12.5px] font-semibold">{{ lane.name }}</span>
                </div>
                <div
                  class="relative space-y-1.5 rounded-xl border p-2.5 transition-all duration-150"
                  :class="[
                    ORCHESTRATOR_TYPE_META[lane.type].border,
                    laneHover === lane.key ? 'border-accent bg-accent/10' : 'bg-white/[0.015]',
                  ]"
                  :style="{ boxShadow: `inset 3px 0 0 0 ${ORCHESTRATOR_TYPE_META[lane.type].bar}` }"
                  @dragover="onLaneDragOver($event, lane.key)"
                  @dragleave="onLaneDragLeave($event, lane.key)"
                  @drop="onLaneDrop($event, lane.key)"
                >
                  <!-- 提取器泳道（pre/post） -->
                  <template v-if="lane.type === 'extractor'">
                    <StrategyStageNode
                      v-for="(entry, idx) in laneEntries(lane)"
                      :key="`${lane.key}:${idx}`"
                      :lane="lane.key"
                      :idx="idx"
                      :component="findComponent('extractor', entry.id)"
                      :seq="seqMap.get(`${lane.key}:${idx}`) ?? 0"
                      :llm="entry.llm"
                      :llm-options="chatModelOptions"
                      :entry-count="laneEntries(lane).length"
                      :params-open="!!openParams[`${lane.key}:${idx}`]"
                      :params="entry.params"
                      :param-fields="EXTRACTOR_PARAM_FIELDS[entry.id] ?? []"
                      :scope="extractorScope(lane)"
                      :dragging="draggingKey === `${lane.key}:${idx}`"
                      :drop-mark="dropMark"
                      :readonly="readonly"
                      @drag-start="onNodeDragStart"
                      @drag-end="onDragEnd"
                      @drag-over="onNodeDragOver"
                      @drop="onNodeDrop"
                      @toggle-params="toggleParams"
                      @shift="shift"
                      @remove="removeEntry"
                      @switch-scope="switchScope"
                      @set-llm="setEntryLlm"
                      @set-param="setParam"
                    />
                    <p
                      v-if="!laneEntries(lane).length"
                      class="rounded-lg border border-dashed border-white/10 px-3 py-3 text-center text-[11.5px] text-muted"
                    >
                      {{ readonly ? '暂无组件' : '可选1个或多个 · 从左侧「提取器」分组点击 + 或拖入' }}
                    </p>
                  </template>
                  <!-- 解析器 / 分块器泳道 -->
                  <template v-else>
                    <StrategyStageNode
                      v-for="(entry, idx) in laneComponentEntries(lane)"
                      :key="`${lane.key}:${idx}`"
                      :lane="lane.key"
                      :idx="idx"
                      :component="findComponent(lane.type, entry.id)"
                      :seq="seqMap.get(`${lane.key}:${idx}`) ?? 0"
                      :entry-count="laneComponentEntries(lane).length"
                      :params-open="!!openParams[`${lane.key}:${idx}`]"
                      :params="entry.params"
                      :param-fields="CHUNKER_PARAM_FIELDS[entry.id] ?? []"
                      :inherited-embed-model="entry.id === 'semantic' ? embedModelDisplay : undefined"
                      :scope="null"
                      :dragging="draggingKey === `${lane.key}:${idx}`"
                      :drop-mark="dropMark"
                      :readonly="readonly"
                      @drag-start="onNodeDragStart"
                      @drag-end="onDragEnd"
                      @drag-over="onNodeDragOver"
                      @drop="onNodeDrop"
                      @toggle-params="toggleParams"
                      @shift="shift"
                      @remove="removeEntry"
                      @set-param="setParam"
                    />
                    <p
                      v-if="!laneComponentEntries(lane).length"
                      class="rounded-lg border border-dashed border-white/10 px-3 py-3 text-center text-[11.5px] text-muted"
                    >
                      {{
                        readonly
                          ? '暂无组件'
                          : lane.type === 'parser'
                            ? '必选1个 · 从左侧「解析器」分组点击 + 或拖入'
                            : '必选1个或多个 · 从左侧「分块器」分组点击 + 或拖入'
                      }}
                    </p>
                  </template>
                  <p v-if="lane.key === 'pre'" class="mx-0.5 mt-1.5 text-[10.5px] leading-relaxed text-muted/80">
                    高级能力：摘要 / 主题等需要全文视野的提取器放这里，作用于 Document，结果被所有 chunk
                    继承。默认可保持为空。
                  </p>
                  <p v-else-if="lane.key === 'split'" class="mx-0.5 mt-1.5 text-[10.5px] leading-relaxed text-muted/80">
                    多个分块器按自上而下顺序<strong class="font-semibold text-ink/80">级联</strong
                    >：第 2 级作用于第 1 级产出的每个块。请让块粒度逐级变细。
                  </p>
                  <p v-else-if="lane.key === 'post'" class="mx-0.5 mt-1.5 text-[10.5px] leading-relaxed text-muted/80">
                    提取器位于分块之后，对每个节点各执行一次。留空即「不提取」。
                  </p>
                </div>
              </div>
              <!-- 泳道连接线 -->
              <div v-if="laneIdx < ORCHESTRATOR_LANES.length - 1" class="ml-[26px] h-[18px]" aria-hidden="true">
                <span class="relative block h-full border-l border-dashed border-white/15">
                  <span class="absolute -bottom-px -left-[3.5px] size-[7px] rotate-45 border-b border-r border-white/25" />
                </span>
              </div>
            </template>
          </div>

          <!-- 校验告警（只读详情不展示） -->
          <div v-if="!readonly && alerts.length" class="mt-4 space-y-1.5">
            <div
              v-for="(alert, i) in alerts"
              :key="i"
              class="flex gap-2.5 rounded-lg border px-3 py-2.5 text-[11px] leading-relaxed"
              :class="{
                'border-red-500/25 bg-red-500/[0.07] text-red-300': alert.level === 'error',
                'border-amber-400/25 bg-amber-400/[0.06] text-amber-200/90': alert.level === 'warn',
                'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-200/90': alert.level === 'info',
              }"
            >
              <span class="shrink-0 text-xs">{{ alert.icon }}</span>
              <span>{{ alert.text }}</span>
            </div>
          </div>

          <p
            v-if="errorMessage"
            class="mt-4 flex items-start gap-1.5 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs leading-relaxed text-red-300"
            role="alert"
          >
            <AlertCircle class="mt-0.5 size-3.5 shrink-0" />
            {{ errorMessage }}
          </p>

          <div class="mt-6 flex justify-end gap-2 border-t border-white/8 pt-4">
            <template v-if="!readonly">
              <AppButton variant="ghost" :disabled="submitting" @click="resetAll">
                <RotateCcw class="size-3.5" />
                重置
              </AppButton>
              <AppButton variant="primary" :loading="submitting" @click="onSubmit">保存策略</AppButton>
            </template>
            <AppButton v-else variant="ghost" @click="emit('close')">关闭</AppButton>
          </div>
        </div>
      </main>

      <!-- ============ 执行顺序镜像 ============ -->
      <aside class="flex min-h-0 flex-col border-white/8 max-md:border-t md:border-l">
        <div class="border-b border-white/8 px-4 py-3.5">
          <p class="text-xs font-semibold tracking-wide text-muted">执行顺序 · 唯一真相源</p>
        </div>
        <div class="min-h-0 flex-1 overflow-y-auto px-4 py-3.5">
          <p v-if="!flat.length" class="py-6 text-center text-[11px] text-muted">流程为空，从左侧添加组件</p>
          <div v-for="step in flat" :key="step.seq" class="relative flex gap-2.5 pb-3.5 last:pb-0">
            <span
              v-if="step.seq < flat.length"
              aria-hidden="true"
              class="absolute bottom-0 left-[11px] top-6 w-px bg-gradient-to-b from-white/15 to-white/5"
            />
            <span
              class="z-[1] grid size-[23px] shrink-0 place-items-center rounded-md border text-[10px] font-bold"
              :class="[
                ORCHESTRATOR_TYPE_META[step.type].border,
                ORCHESTRATOR_TYPE_META[step.type].bg,
                ORCHESTRATOR_TYPE_META[step.type].text,
              ]"
            >
              {{ String(step.seq).padStart(2, '0') }}
            </span>
            <span class="min-w-0 pt-0.5">
              <span class="block truncate text-[11.5px] font-semibold">{{ step.component.name }}</span>
              <span class="mt-0.5 block text-[10px] leading-relaxed text-muted/80">
                {{ stepMeta(step.lane, step.idx) }}
              </span>
            </span>
          </div>
        </div>
        <div class="border-t border-white/8 px-4 py-3 text-[10px] leading-relaxed text-muted/80">
          顺序变更、作用域切换、参数修改均实时反映在此处。保存时对整条序列做版本快照。
        </div>
      </aside>
    </div>

    <!-- 操作反馈 Toast -->
    <Transition name="fade">
      <div
        v-if="toastMessage"
        class="pointer-events-none fixed bottom-8 left-1/2 z-[60] -translate-x-1/2 rounded-lg border border-white/10 bg-elevated px-4 py-2.5 text-xs text-ink shadow-[0_12px_40px_rgba(0,0,0,0.5)]"
      >
        {{ toastMessage }}
      </div>
    </Transition>
  </AppModal>
</template>
