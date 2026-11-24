<script setup lang="ts">
/**
 * 知识库图谱schema面板 —— 实体/关系类型定义的查看与维护
 * ------------------------------------------------------------------
 * 每个知识库一份图谱schema：实体（name/desc/properties 属性字段）+ 关系（name/desc/主体→客体）。
 * 构图抽取按此 schema 对齐；策略开启「构建知识图谱」时要求本 schema 已创建，
 * 策略内仅展示不可修改，修改统一在本面板完成。
 */
import { Boxes, Pencil, Plus, Share2, Trash2 } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import * as api from '@/api/knowledge'
import type { GraphSchema, GraphSchemaRelation } from '@/types/knowledge'
import AppButton from '@/components/ui/AppButton.vue'
import AppModal from '@/components/ui/AppModal.vue'
import AppSelect from '@/components/ui/AppSelect.vue'
import EmptyState from '@/components/ui/EmptyState.vue'

const props = defineProps<{ kbId: string }>()

/** 规模上限（与后端校验一致） */
const MAX_ENTITIES = 50
const MAX_RELATIONS = 100
const MAX_PROPERTIES = 50

const loading = ref(true)
const schema = ref<GraphSchema | null>(null)
const loadError = ref('')

/** ---------------- 编辑状态（弹窗内整体编辑，保存时整体覆盖提交） ---------------- */
const editing = ref(false)
const saving = ref(false)
const errorMessage = ref('')
/** 编辑态：属性用数组模型（key/desc 行），保存时再转 Record —— 避免把对象键当输入值源导致重渲染丢焦点 */
interface DraftProperty {
  key: string
  desc: string
}
interface DraftEntity {
  name: string
  desc: string
  props: DraftProperty[]
}
const draftEntities = ref<DraftEntity[]>([])
const draftRelations = ref<GraphSchemaRelation[]>([])

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    schema.value = await api.getGraphSchema(props.kbId)
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '加载图谱schema失败，请稍后重试'
    schema.value = null
  } finally {
    loading.value = false
  }
}

watch(() => props.kbId, load, { immediate: true })

defineExpose({ reload: load })

function openEdit() {
  const current = schema.value
  draftEntities.value = current
    ? current.entities.map((entity) => ({
        name: entity.name,
        desc: entity.desc,
        props: Object.entries(entity.properties).map(([key, desc]) => ({ key, desc })),
      }))
    : []
  draftRelations.value = current
    ? current.relations.map((relation) => ({ ...relation }))
    : []
  errorMessage.value = ''
  editing.value = true
}

/** ---------------- 实体编辑 ---------------- */
function addEntity() {
  if (draftEntities.value.length >= MAX_ENTITIES) return
  draftEntities.value.push({ name: '', desc: '', props: [] })
}

function removeEntity(idx: number) {
  const [removed] = draftEntities.value.splice(idx, 1)
  // 关系中引用了被删实体类型的起点/终点一并清空，避免提交脏数据
  for (const relation of draftRelations.value) {
    if (relation.subjectType === removed.name) relation.subjectType = ''
    if (relation.objectType === removed.name) relation.objectType = ''
  }
}

function addProperty(entity: DraftEntity) {
  if (entity.props.length >= MAX_PROPERTIES) return
  entity.props.push({ key: '', desc: '' })
}

function removeProperty(entity: DraftEntity, idx: number) {
  entity.props.splice(idx, 1)
}

/** ---------------- 关系编辑 ---------------- */
function addRelation() {
  if (draftRelations.value.length >= MAX_RELATIONS) return
  draftRelations.value.push({ name: '', desc: '', subjectType: '', objectType: '' })
}

function removeRelation(idx: number) {
  draftRelations.value.splice(idx, 1)
}

/** 实体类型下拉选项（关系中起点/终点可选范围） */
const entityTypeOptions = computed(() =>
  draftEntities.value
    .filter((entity) => entity.name.trim())
    .map((entity) => ({ value: entity.name.trim(), label: entity.name.trim() })),
)

/** ---------------- 保存 ---------------- */
async function onSave() {
  errorMessage.value = ''
  const entities = draftEntities.value.map((entity) => ({
    name: entity.name.trim(),
    desc: entity.desc.trim(),
    properties: Object.fromEntries(
      entity.props
        .map((prop) => [prop.key.trim(), prop.desc.trim()])
        .filter(([key]) => key),
    ),
  }))
  const relations = draftRelations.value.map((relation) => ({
    name: relation.name.trim(),
    desc: relation.desc.trim(),
    subjectType: relation.subjectType.trim(),
    objectType: relation.objectType.trim(),
  }))

  const names = new Set<string>()
  for (const entity of entities) {
    if (!entity.name) {
      errorMessage.value = '实体类型名不能为空'
      return
    }
    if (names.has(entity.name)) {
      errorMessage.value = `实体类型「${entity.name}」重复定义`
      return
    }
    names.add(entity.name)
    const propKeys = new Set<string>()
    for (const key of Object.keys(entity.properties)) {
      if (propKeys.has(key)) {
        errorMessage.value = `实体类型「${entity.name}」属性名「${key}」重复`
        return
      }
      propKeys.add(key)
    }
  }
  const relNames = new Set<string>()
  for (const relation of relations) {
    if (!relation.name) {
      errorMessage.value = '关系类型名不能为空'
      return
    }
    if (relNames.has(relation.name)) {
      errorMessage.value = `关系类型「${relation.name}」重复定义`
      return
    }
    relNames.add(relation.name)
    if (!names.has(relation.subjectType) || !names.has(relation.objectType)) {
      errorMessage.value = `关系「${relation.name}」的起点/终点必须为已定义的实体类型`
      return
    }
  }
  if (!entities.length) {
    errorMessage.value = '图谱schema至少需要定义一个实体类型'
    return
  }

  saving.value = true
  try {
    schema.value = await api.saveGraphSchema(props.kbId, { entities, relations })
    editing.value = false
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '保存图谱schema失败，请稍后重试'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <p
      v-if="loadError"
      class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2.5 text-xs leading-relaxed text-red-300"
      role="alert"
    >
      {{ loadError }}
    </p>

    <!-- 工具栏：说明 + 创建/编辑 -->
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div class="min-w-0">
        <h2 class="flex items-center gap-2 text-sm font-medium">
          <Boxes class="size-4 text-accent" :stroke-width="1.75" />
          图谱schema
        </h2>
        <p class="mt-1 text-xs leading-relaxed text-muted">
          定义知识库图谱的实体与关系类型，构图抽取按此 schema 对齐；
          策略开启「构建知识图谱」时将引用此 schema（策略内不可修改）。
        </p>
      </div>
      <AppButton variant="primary" class="ml-auto" :loading="loading" @click="openEdit">
        <Pencil class="size-4" />
        {{ schema ? '编辑schema' : '创建schema' }}
      </AppButton>
    </header>

    <!-- 骨架屏 -->
    <section v-if="loading" class="card-surface animate-pulse p-2" aria-busy="true">
      <div v-for="i in 3" :key="i" class="flex items-center gap-4 px-4 py-4">
        <div class="size-9 rounded-lg bg-white/5" />
        <div class="h-3.5 w-1/3 rounded bg-white/5" />
      </div>
    </section>

    <!-- schema 展示 -->
    <template v-else-if="schema">
      <!-- 实体类型 -->
      <section class="mt-5 space-y-3">
        <h3 class="flex items-center gap-2 text-[13px] font-semibold">
          <Boxes class="size-3.5 text-accent" :stroke-width="1.75" />
          实体类型
          <span class="font-mono text-[11px] font-normal text-muted">{{ schema.entities.length }}</span>
        </h3>
        <div class="grid gap-3 md:grid-cols-2">
          <div
            v-for="entity in schema.entities"
            :key="entity.name"
            class="rounded-xl border border-white/8 bg-white/[0.02] p-4"
          >
            <div class="flex items-baseline gap-2">
              <span class="font-mono text-sm font-semibold text-indigo-300">{{ entity.name }}</span>
              <span v-if="entity.desc" class="min-w-0 truncate text-xs text-muted">{{ entity.desc }}</span>
            </div>
            <div v-if="Object.keys(entity.properties).length" class="mt-3 space-y-1">
              <div
                v-for="(propDesc, propName) in entity.properties"
                :key="propName"
                class="flex items-baseline gap-2 text-[11.5px]"
              >
                <span class="shrink-0 rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-ink/85">
                  {{ propName }}
                </span>
                <span class="min-w-0 truncate text-muted">{{ propDesc }}</span>
              </div>
            </div>
            <p v-else class="mt-3 text-[11px] text-muted/70">无属性字段</p>
          </div>
        </div>
      </section>

      <!-- 关系类型 -->
      <section class="mt-6 space-y-3">
        <h3 class="flex items-center gap-2 text-[13px] font-semibold">
          <Share2 class="size-3.5 text-accent" :stroke-width="1.75" />
          关系类型
          <span class="font-mono text-[11px] font-normal text-muted">{{ schema.relations.length }}</span>
        </h3>
        <div
          v-if="schema.relations.length"
          class="divide-y divide-white/6 overflow-hidden rounded-xl border border-white/8 bg-white/[0.02]"
        >
          <div
            v-for="relation in schema.relations"
            :key="relation.name"
            class="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3"
          >
            <span class="font-mono text-[12.5px] font-semibold text-indigo-300">{{ relation.name }}</span>
            <span class="text-[11.5px] text-muted">{{ relation.desc }}</span>
            <span class="ml-auto flex items-center gap-1.5 font-mono text-[11px] text-muted">
              <span class="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5">{{ relation.subjectType }}</span>
              <span aria-hidden="true">→</span>
              <span class="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5">{{ relation.objectType }}</span>
            </span>
          </div>
        </div>
        <p v-else class="rounded-xl border border-dashed border-white/10 px-4 py-3 text-[11.5px] text-muted">
          未定义关系类型，构图时不约束关系。
        </p>
      </section>
    </template>

    <!-- 空状态 -->
    <section v-else class="mt-5">
      <EmptyState
        title="尚未创建图谱schema"
        description="定义实体（含属性字段）与关系类型后，策略方可开启构建知识图谱。"
      >
        <template #icon><Boxes class="size-6" :stroke-width="1.5" /></template>
        <template #action>
          <AppButton variant="primary" @click="openEdit">
            <Plus class="size-4" />
            创建schema
          </AppButton>
        </template>
      </EmptyState>
    </section>

    <!-- 编辑弹窗 -->
    <AppModal
      :open="editing"
      :title="schema ? '编辑图谱schema' : '创建图谱schema'"
      width="max-w-[860px]"
      @close="editing = false"
    >
      <div class="max-h-[60vh] space-y-6 overflow-y-auto pr-1">
        <!-- 实体类型编辑 -->
        <section class="space-y-3">
          <div class="flex items-baseline justify-between gap-2">
            <h3 class="text-sm font-semibold">实体类型</h3>
            <span class="font-mono text-[11px] text-muted">
              {{ draftEntities.length }}/{{ MAX_ENTITIES }}
            </span>
          </div>
          <div
            v-for="(entity, idx) in draftEntities"
            :key="idx"
            class="space-y-2.5 rounded-xl border border-white/10 bg-white/[0.02] p-3"
          >
            <div class="flex items-center gap-2">
              <input
                v-model="entity.name"
                placeholder="实体类型名，例如：Device"
                class="h-8 w-44 rounded-lg border border-white/10 bg-input px-2.5 font-mono text-xs text-ink outline-none transition-all duration-200 placeholder:text-muted/60 focus:border-accent focus:shadow-[0_0_0_3px_rgba(94,106,210,0.25)]"
                :aria-label="`第 ${idx + 1} 个实体类型名`"
              />
              <input
                v-model="entity.desc"
                placeholder="实体描述，例如：电力设备"
                class="h-8 min-w-0 flex-1 rounded-lg border border-white/10 bg-input px-2.5 text-xs text-ink outline-none transition-all duration-200 placeholder:text-muted/60 focus:border-accent focus:shadow-[0_0_0_3px_rgba(94,106,210,0.25)]"
                :aria-label="`第 ${idx + 1} 个实体描述`"
              />
              <button
                type="button"
                class="grid size-[22px] shrink-0 place-items-center rounded-md text-[11px] text-muted transition-colors duration-200 hover:bg-red-500/10 hover:text-red-300"
                title="移除实体类型"
                :aria-label="`移除第 ${idx + 1} 个实体类型`"
                @click="removeEntity(idx)"
              >
                ×
              </button>
            </div>
            <!-- 属性字段（数组行编辑，保存时转为 属性名→描述 映射） -->
            <div class="space-y-1.5">
              <p class="font-mono text-[10.5px] text-muted">
                属性字段
                <span class="ml-1 text-muted/70">
                  {{ entity.props.length }}/{{ MAX_PROPERTIES }}
                </span>
              </p>
              <div
                v-for="(prop, propIdx) in entity.props"
                :key="propIdx"
                class="flex items-center gap-1.5"
              >
                <input
                  v-model="prop.key"
                  placeholder="属性名，例如：code"
                  class="h-7 w-40 rounded-lg border border-white/10 bg-input px-2.5 font-mono text-[11px] text-ink outline-none transition-all duration-200 placeholder:text-muted/60 focus:border-accent"
                  aria-label="属性名"
                />
                <input
                  v-model="prop.desc"
                  placeholder="属性描述，例如：设备编号"
                  class="h-7 min-w-0 flex-1 rounded-lg border border-white/10 bg-input px-2.5 text-[11px] text-ink outline-none transition-all duration-200 placeholder:text-muted/60 focus:border-accent"
                  aria-label="属性描述"
                />
                <button
                  type="button"
                  class="grid size-[22px] shrink-0 place-items-center rounded-md text-[11px] text-muted transition-colors duration-200 hover:bg-red-500/10 hover:text-red-300"
                  title="移除属性"
                  :aria-label="`移除属性 ${prop.key || '未命名'}`"
                  @click="removeProperty(entity, propIdx)"
                >
                  <Trash2 class="size-3" />
                </button>
              </div>
              <button
                type="button"
                class="flex items-center gap-1 rounded-lg border border-dashed border-white/15 px-2 py-1 text-[10.5px] text-muted transition-colors duration-200 hover:border-accent/50 hover:text-ink"
                @click="addProperty(entity)"
              >
                <Plus class="size-3" />
                添加属性
              </button>
            </div>
          </div>
          <button
            type="button"
            class="flex w-full items-center justify-center gap-1 rounded-xl border border-dashed border-white/15 py-2 text-[11.5px] text-muted transition-colors duration-200 hover:border-accent/50 hover:text-ink"
            @click="addEntity"
          >
            <Plus class="size-3.5" />
            添加实体类型
          </button>
        </section>

        <!-- 关系类型编辑 -->
        <section class="space-y-3">
          <div class="flex items-baseline justify-between gap-2">
            <h3 class="text-sm font-semibold">关系类型</h3>
            <span class="font-mono text-[11px] text-muted">
              {{ draftRelations.length }}/{{ MAX_RELATIONS }}
            </span>
          </div>
          <div
            v-for="(relation, idx) in draftRelations"
            :key="idx"
            class="flex flex-wrap items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.02] p-3"
          >
            <input
              v-model="relation.name"
              placeholder="关系名，例如：hasPoint"
              class="h-8 w-40 rounded-lg border border-white/10 bg-input px-2.5 font-mono text-xs text-ink outline-none transition-all duration-200 placeholder:text-muted/60 focus:border-accent focus:shadow-[0_0_0_3px_rgba(94,106,210,0.25)]"
              :aria-label="`第 ${idx + 1} 条关系名`"
            />
            <input
              v-model="relation.desc"
              placeholder="关系描述，例如：设备包含测点"
              class="h-8 min-w-0 flex-1 rounded-lg border border-white/10 bg-input px-2.5 text-xs text-ink outline-none transition-all duration-200 placeholder:text-muted/60 focus:border-accent focus:shadow-[0_0_0_3px_rgba(94,106,210,0.25)]"
              :aria-label="`第 ${idx + 1} 条关系描述`"
            />
            <AppSelect
              v-model="relation.subjectType"
              :options="entityTypeOptions"
              placeholder="主体实体"
              size="sm"
              class="w-[120px] shrink-0"
              :aria-label="`第 ${idx + 1} 条关系主体`"
            />
            <span class="shrink-0 text-[11px] text-muted/70" aria-hidden="true">→</span>
            <AppSelect
              v-model="relation.objectType"
              :options="entityTypeOptions"
              placeholder="客体实体"
              size="sm"
              class="w-[120px] shrink-0"
              :aria-label="`第 ${idx + 1} 条关系客体`"
            />
            <button
              type="button"
              class="grid size-[22px] shrink-0 place-items-center rounded-md text-[11px] text-muted transition-colors duration-200 hover:bg-red-500/10 hover:text-red-300"
              title="移除关系"
              :aria-label="`移除第 ${idx + 1} 条关系`"
              @click="removeRelation(idx)"
            >
              ×
            </button>
          </div>
          <button
            type="button"
            class="flex w-full items-center justify-center gap-1 rounded-xl border border-dashed border-white/15 py-2 text-[11.5px] text-muted transition-colors duration-200 hover:border-accent/50 hover:text-ink"
            @click="addRelation"
          >
            <Plus class="size-3.5" />
            添加关系类型
          </button>
        </section>

        <p
          v-if="errorMessage"
          class="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs leading-relaxed text-red-300"
          role="alert"
        >
          {{ errorMessage }}
        </p>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <AppButton variant="ghost" :disabled="saving" @click="editing = false">取消</AppButton>
          <AppButton variant="primary" :loading="saving" @click="onSave">
            {{ schema ? '保存修改' : '创建schema' }}
          </AppButton>
        </div>
      </template>
    </AppModal>
  </div>
</template>
