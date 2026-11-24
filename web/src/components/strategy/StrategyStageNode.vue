<script setup lang="ts">
/**
 * 编排泳道内的组件卡片：拖拽手柄 / 全局序号 / 名称 / 级别与作用域徽标 /
 * 参数展开（点击主体或分块器的设置按钮）/ LLM 选择（提取器）/
 * 分块器参数编辑面板 / 上移·下移·移除·作用域切换。
 * 自身不修改状态，全部通过事件回调交由父组件（编排器）处理。
 */
import { computed } from 'vue'
import { GripVertical, Settings2 } from '@lucide/vue'
import AppSelect from '@/components/ui/AppSelect.vue'
import type { ChunkerParamField, OrchestratorComponent, OrchestratorLane } from './options'

type LaneKey = OrchestratorLane['key']

const props = defineProps<{
  lane: LaneKey
  idx: number
  component: OrchestratorComponent
  /** 全局执行序号（1 起） */
  seq: number
  /** 执行LLM（仅提取器有值） */
  llm?: string
  llmOptions?: { value: string; label: string }[]
  entryCount: number
  paramsOpen?: boolean
  /** 分块器参数配置（paramFields 有值时用于参数面板回显） */
  params?: Record<string, number | string>
  /** 分块器可编辑参数字段定义（无可配置参数的分块器为空数组） */
  paramFields?: ChunkerParamField[]
  /** 策略继承的嵌入模型展示名（语义分块等依赖嵌入模型的分块器展示，只读） */
  inheritedEmbedModel?: string
  /** 提取器作用域：pre = 文档级 / post = 块级；解析器与分块器为 null */
  scope?: 'pre' | 'post' | null
  dragging?: boolean
  dropMark?: { lane: string; idx: number; after: boolean } | null
  /** 只读详情模式：隐藏拖拽/排序/移除等操作控件，LLM 以文本展示 */
  readonly?: boolean
}>()

const emit = defineEmits<{
  'drag-start': [event: DragEvent, lane: LaneKey, idx: number, id: string]
  'drag-end': []
  'drag-over': [event: DragEvent, lane: LaneKey, idx: number]
  drop: [event: DragEvent, lane: LaneKey, idx: number]
  'toggle-params': [key: string]
  shift: [lane: LaneKey, idx: number, delta: number]
  remove: [lane: LaneKey, idx: number]
  'switch-scope': [lane: LaneKey, idx: number]
  'set-llm': [lane: LaneKey, idx: number, llm: string]
  'set-param': [lane: LaneKey, idx: number, key: string, value: number | string]
}>()

const isSplitter = computed(() => props.lane === 'split')
const isExtractor = computed(() => props.scope !== null && props.scope !== undefined)
const hasParamFields = computed(() => (props.paramFields?.length ?? 0) > 0)

/** 参数生效值：未配置的键显示默认值 */
function paramValue(field: ChunkerParamField): number | string {
  const value = props.params?.[field.key]
  return value === undefined || value === '' ? field.default : value
}

/** 参数是否已自定义（只读详情的徽标展示） */
function isCustomized(field: ChunkerParamField): boolean {
  const value = props.params?.[field.key]
  return value !== undefined && value !== ''
}

function onParamInput(field: ChunkerParamField, event: Event) {
  const raw = (event.target as HTMLInputElement).value
  if (raw === '') {
    emit('set-param', props.lane, props.idx, field.key, '')
    return
  }
  const value = field.type === 'number' ? Number(raw) : raw
  emit('set-param', props.lane, props.idx, field.key, Number.isNaN(value as number) ? raw : value)
}

const dropBefore = computed(
  () => props.dropMark?.lane === props.lane && props.dropMark?.idx === props.idx && !props.dropMark?.after,
)
const dropAfter = computed(
  () => props.dropMark?.lane === props.lane && props.dropMark?.idx === props.idx && props.dropMark?.after,
)
</script>

<template>
  <div
    class="relative flex items-center gap-2.5 rounded-lg border bg-white/[0.04] px-3 py-2.5 transition-all duration-150"
    :class="[
      props.dragging ? 'opacity-35' : 'hover:bg-white/[0.06]',
      dropBefore
        ? 'stage-drop-before border-accent'
        : dropAfter
          ? 'stage-drop-after border-accent'
          : 'border-white/10',
    ]"
    :draggable="!props.readonly"
    @dragstart="emit('drag-start', $event, props.lane, props.idx, props.component.id)"
    @dragend="emit('drag-end')"
    @dragover="emit('drag-over', $event, props.lane, props.idx)"
    @drop="emit('drop', $event, props.lane, props.idx)"
  >
    <span v-if="!props.readonly" class="cursor-grab select-none text-muted/60 active:cursor-grabbing" title="拖拽排序">
      <GripVertical class="size-3.5" />
    </span>
    <span
      class="grid size-[22px] shrink-0 place-items-center rounded-md border border-accent/45 bg-accent/10 text-[10.5px] font-bold text-indigo-300"
    >
      {{ String(props.seq).padStart(2, '0') }}
    </span>
    <span class="grid size-7 shrink-0 place-items-center rounded-md border border-white/8 bg-white/[0.04] text-ink/80">
      <component :is="props.component.icon" class="size-4" :stroke-width="1.75" />
    </span>
    <button
      type="button"
      class="min-w-0 flex-1 cursor-pointer text-left"
      :title="props.paramsOpen ? '收起参数' : '展开参数'"
      @click="emit('toggle-params', `${props.lane}:${props.idx}`)"
    >
      <span class="flex flex-wrap items-center gap-1.5">
        <span class="text-[12.5px] font-semibold">{{ props.component.name }}</span>
        <span
          v-if="isSplitter && props.idx > 0"
          class="rounded-full border border-indigo-400/35 bg-indigo-400/10 px-2 py-px text-[9.5px] text-indigo-300"
        >
          第 {{ props.idx + 1 }} 级切分
        </span>
        <span
          v-if="props.scope === 'pre'"
          class="rounded-full border border-amber-400/35 bg-amber-400/10 px-2 py-px text-[9.5px] text-amber-300"
        >
          文档级 · 1 次/文档
        </span>
        <span
          v-else-if="props.scope === 'post'"
          class="rounded-full border border-amber-400/35 bg-amber-400/10 px-2 py-px text-[9.5px] text-amber-300"
        >
          块级 · 1 次/块
        </span>
      </span>
      <span class="mt-0.5 block truncate text-[10.5px] text-muted/80">{{ props.component.description }}</span>
    </button>
    <div v-if="isExtractor" class="llm-inline flex shrink-0 items-center gap-1.5">
      <span class="whitespace-nowrap text-[10.5px] text-muted/80">LLM：</span>
      <span v-if="props.readonly" class="max-w-[160px] truncate text-[11px] text-ink/85">
        {{ props.llm || '不使用' }}
      </span>
      <AppSelect
        v-else
        :model-value="props.llm ?? ''"
        :options="props.llmOptions ?? []"
        size="sm"
        class="w-[150px]"
        :aria-label="`${props.component.name} 执行 LLM`"
        @click.stop
        @dragstart.stop
        @update:model-value="emit('set-llm', props.lane, props.idx, $event)"
      />
    </div>
    <div v-if="!props.readonly" class="flex shrink-0 items-center gap-0.5">
      <button
        v-if="hasParamFields"
        type="button"
        class="grid size-[22px] place-items-center rounded-md text-muted transition-colors duration-200 hover:bg-white/8 hover:text-ink"
        :class="props.paramsOpen ? 'bg-white/8 text-ink' : ''"
        :title="props.paramsOpen ? '收起参数配置' : '参数配置'"
        :aria-label="`配置 ${props.component.name} 参数`"
        @click.stop
        @dragstart.stop
        @click="emit('toggle-params', `${props.lane}:${props.idx}`)"
      >
        <Settings2 class="size-3.5" />
      </button>
      <button
        v-if="isExtractor"
        type="button"
        class="grid size-[22px] place-items-center rounded-md text-[11px] text-muted transition-colors duration-200 hover:bg-white/8 hover:text-ink"
        :title="props.scope === 'pre' ? '切换为块级提取' : '切换为文档级提取'"
        :aria-label="`切换 ${props.component.name} 作用域`"
        @click="emit('switch-scope', props.lane, props.idx)"
      >
        ⇅
      </button>
      <button
        type="button"
        class="grid size-[22px] place-items-center rounded-md text-[11px] text-muted transition-colors duration-200 hover:bg-white/8 hover:text-ink disabled:opacity-20 disabled:hover:bg-transparent"
        :disabled="props.idx === 0"
        title="上移"
        :aria-label="`上移 ${props.component.name}`"
        @click="emit('shift', props.lane, props.idx, -1)"
      >
        ↑
      </button>
      <button
        type="button"
        class="grid size-[22px] place-items-center rounded-md text-[11px] text-muted transition-colors duration-200 hover:bg-white/8 hover:text-ink disabled:opacity-20 disabled:hover:bg-transparent"
        :disabled="props.idx === props.entryCount - 1"
        title="下移"
        :aria-label="`下移 ${props.component.name}`"
        @click="emit('shift', props.lane, props.idx, 1)"
      >
        ↓
      </button>
      <button
        type="button"
        class="grid size-[22px] place-items-center rounded-md text-[11px] text-muted transition-colors duration-200 hover:bg-red-500/10 hover:text-red-300"
        title="移除"
        :aria-label="`移除 ${props.component.name}`"
        @click="emit('remove', props.lane, props.idx)"
      >
        ×
      </button>
    </div>
    <!-- 参数面板：分块器为可编辑参数表单，其余组件展示固定配置（点击主体/设置按钮展开） -->
    <div
      v-if="props.paramsOpen && (hasParamFields || props.component.params.length)"
      class="absolute inset-x-3 top-full z-10 mt-1 rounded-lg border border-white/8 bg-elevated px-3 py-2.5 shadow-[0_8px_24px_rgba(0,0,0,0.45)]"
    >
      <div v-if="hasParamFields" class="space-y-2">
        <!-- 依赖嵌入模型的分块器（语义分块）：嵌入模型继承自策略（知识库），只读不可改 -->
        <div
          v-if="props.inheritedEmbedModel"
          class="flex items-center gap-2"
          title="语义分块依赖嵌入模型计算相邻句组相似度；使用策略继承的知识库嵌入模型，不可单独修改"
        >
          <span class="w-[112px] shrink-0 text-[10.5px] text-muted/80">嵌入模型（继承）</span>
          <div
            class="min-w-0 flex-1 cursor-default truncate rounded-md border border-white/10 bg-input px-2 py-1 text-[11px] text-ink/85"
          >
            {{ props.inheritedEmbedModel }}
          </div>
          <span
            class="shrink-0 rounded-full border border-emerald-400/35 bg-emerald-400/10 px-1.5 py-px text-[9px] text-emerald-300"
          >
            继承
          </span>
        </div>
        <div
          v-for="field in props.paramFields"
          :key="field.key"
          class="flex items-center gap-2"
          :title="field.hint"
        >
          <span class="w-[112px] shrink-0 text-[10.5px] text-muted/80">{{ field.label }}</span>
          <input
            v-if="field.type !== 'select' && props.readonly"
            :value="String(paramValue(field))"
            readonly
            class="w-full min-w-0 flex-1 cursor-default rounded-md border border-white/10 bg-input px-2 py-1 text-[11px] text-ink/85 outline-none"
          />
          <input
            v-else-if="field.type === 'number'"
            :value="String(paramValue(field))"
            type="number"
            :min="field.min"
            :max="field.max"
            :step="field.step ?? 1"
            :placeholder="String(field.default)"
            class="w-full min-w-0 flex-1 rounded-md border border-white/10 bg-input px-2 py-1 text-[11px] text-ink outline-none transition-colors duration-200 placeholder:text-muted/60 focus:border-accent/50"
            @click.stop
            @dragstart.stop
            @change="onParamInput(field, $event)"
          />
          <input
            v-else-if="field.type === 'text'"
            :value="String(paramValue(field))"
            type="text"
            :placeholder="field.placeholder"
            class="w-full min-w-0 flex-1 rounded-md border border-white/10 bg-input px-2 py-1 text-[11px] text-ink outline-none transition-colors duration-200 placeholder:text-muted/60 focus:border-accent/50"
            @click.stop
            @dragstart.stop
            @change="onParamInput(field, $event)"
          />
          <AppSelect
            v-else
            :model-value="String(paramValue(field))"
            :options="field.options ?? []"
            size="sm"
            class="w-full min-w-0 flex-1"
            :aria-label="field.label"
            @click.stop
            @dragstart.stop
            @update:model-value="emit('set-param', props.lane, props.idx, field.key, $event)"
          />
          <span
            v-if="props.readonly && isCustomized(field)"
            class="shrink-0 rounded-full border border-indigo-400/35 bg-indigo-400/10 px-1.5 py-px text-[9px] text-indigo-300"
          >
            自定义
          </span>
        </div>
        <p v-if="!props.readonly" class="pt-0.5 text-[10px] leading-relaxed text-muted/70">
          留空或未修改的参数按默认值生效；悬停参数名查看说明。
        </p>
      </div>
      <div v-else class="flex flex-wrap gap-x-5 gap-y-2">
        <div v-for="[k, v] in props.component.params" :key="k">
          <div class="text-[10px] text-muted/70">{{ k }}</div>
          <div class="mt-0.5 text-[11px] text-ink/85">{{ v }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 拖拽插入线（drop-before/after） */
.stage-drop-before::before,
.stage-drop-after::after {
  content: '';
  position: absolute;
  left: 6px;
  right: 6px;
  height: 2px;
  background: var(--color-accent);
  border-radius: 2px;
  box-shadow: 0 0 8px var(--color-accent);
  z-index: 1;
}
.stage-drop-before::before {
  top: -6px;
}
.stage-drop-after::after {
  bottom: -6px;
}
</style>
