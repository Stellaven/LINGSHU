<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { BadgeCheck, KeyRound, Pencil, PlugZap, Plus, Search } from '@lucide/vue'
import { testProviderConnection } from '@/api/models'
import type { ModelProvider, ProviderModel } from '@/types/models'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppSelect from '@/components/ui/AppSelect.vue'
import ConfirmModal from '@/components/ui/ConfirmModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import {
  createInstance,
  ensureProviders,
  loaded,
  providers,
  removeInstance,
  saveInstance,
  selectProvider,
  selectedProvider,
  syncModels,
  updateModel,
} from '@/stores/models'

const route = useRoute()
const projectId = route.params.projectId as string

/** 提供商状态：已保存实例（点亮绿色）/ 无实例（熄灭） */
type ProviderStatus = 'configured' | 'unconfigured'

/** 已保存模型实例（存在于后端实例列表）即为已配置，状态点点亮为绿色 */
const statusOf = (p: ModelProvider): ProviderStatus =>
  p.instances.length > 0 ? 'configured' : 'unconfigured'

/** 已保存模型实例的状态点：点亮为绿色；无实例时熄灭 */
const STATUS_DOT: Record<ProviderStatus, string> = {
  configured: 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.85)]',
  unconfigured: 'bg-white/15',
}

/** ---------------- 提供商模糊搜索 ---------------- */
const search = ref('')

/** 忽略大小写：子串包含，或按字符顺序的子序列匹配（如 "ds" 命中 DeepSeek） */
function fuzzyMatch(haystack: string, needle: string): boolean {
  const h = haystack.toLowerCase()
  const n = needle.toLowerCase().trim()
  if (!n) return true
  if (h.includes(n)) return true
  let i = 0
  for (const ch of h) {
    if (ch === n[i]) i += 1
    if (i === n.length) return true
  }
  return false
}

const filteredProviders = computed(() =>
  providers.value.filter((p) => fuzzyMatch(p.name, search.value)),
)

/** Base URL 输入占位提示：使用当前提供商官方默认地址 */
const defaultBaseUrlPlaceholder = computed(
  () => `默认：${selectedProvider.value?.defaultBaseUrl ?? 'https://'}`,
)

onMounted(() => {
  void ensureProviders(projectId)
})

/** ---------------- 模型实例表单 ---------------- */
/** 页面内实例卡片状态：已保存实例以 persistedId 标识，新实例 persistedId 为空 */
interface InstanceForm {
  key: string
  persistedId: string | null
  name: string
  baseUrl: string
  /** 仅本地输入，保存后清空（后端不回显明文 Key） */
  apiKey: string
  apiKeyConfigured: boolean
  models: ProviderModel[]
  saving: boolean
  justSaved: boolean
  /** 测试连接状态 */
  testing: boolean
  testOk: boolean | null
  testMessage: string
}

const forms = reactive<InstanceForm[]>([])
let draftSeq = 0

/** 切换提供商时按后端返回的实例列表重建卡片，丢弃未保存的草稿与输入 */
watch(
  () => selectedProvider.value?.id,
  () => {
    forms.splice(0, forms.length)
    for (const inst of selectedProvider.value?.instances ?? []) {
      forms.push({
        key: inst.id,
        persistedId: inst.id,
        name: inst.name,
        baseUrl: inst.baseUrl,
        apiKey: '',
        apiKeyConfigured: inst.apiKeyConfigured,
        models: inst.models,
        saving: false,
        justSaved: false,
        testing: false,
        testOk: null,
        testMessage: '',
      })
    }
  },
  { immediate: true },
)

/** 添加一个尚未保存的实例卡片（始终位于实例列表底部） */
function addInstance() {
  const provider = selectedProvider.value
  if (!provider) return
  draftSeq += 1
  forms.push({
    key: `draft-${draftSeq}`,
    persistedId: null,
    name: `${provider.name} 实例 ${forms.length + 1}`,
    baseUrl: '',
    apiKey: '',
    apiKeyConfigured: false,
    models: [],
    saving: false,
    justSaved: false,
    testing: false,
    testOk: null,
    testMessage: '',
  })
}

/** 删除草稿：直接移除；已保存实例：弹窗确认后调用接口删除 */
const pendingDelete = ref<InstanceForm | null>(null)
const deleting = ref(false)

function onDelete(form: InstanceForm) {
  if (!form.persistedId) {
    const index = forms.indexOf(form)
    if (index >= 0) forms.splice(index, 1)
    return
  }
  pendingDelete.value = form
}

async function confirmDelete() {
  const provider = selectedProvider.value
  const form = pendingDelete.value
  if (!provider || !form?.persistedId || deleting.value) return
  deleting.value = true
  try {
    await removeInstance(projectId, provider.id, form.persistedId)
    const index = forms.indexOf(form)
    if (index >= 0) forms.splice(index, 1)
    pendingDelete.value = null
  } finally {
    deleting.value = false
  }
}

/** 保存实例：新建走创建接口，已有实例走更新接口；API Key 仅在填写时提交 */
async function onSave(form: InstanceForm) {
  const provider = selectedProvider.value
  if (!provider || form.saving) return
  const name = form.name.trim()
  if (!name) return

  form.saving = true
  try {
    const apiKey = form.apiKey.trim()
    if (form.persistedId) {
      const updated = await saveInstance(projectId, provider.id, form.persistedId, {
        name,
        baseUrl: form.baseUrl.trim(),
        ...(apiKey ? { apiKey } : {}),
      })
      form.name = updated.name
      form.baseUrl = updated.baseUrl
      form.apiKeyConfigured = updated.apiKeyConfigured
    } else {
      const testedModels = form.models
      const created = await createInstance(projectId, provider.id, {
        name,
        ...(apiKey ? { apiKey } : {}),
        ...(form.baseUrl.trim() ? { baseUrl: form.baseUrl.trim() } : {}),
        // 测试连接获取的目录随实例一并落库
        ...(testedModels.length
          ? { models: testedModels.map((model) => ({ name: model.name, modelType: model.modelType })) }
          : {}),
      })
      // 新建成功后转为已持久化实例卡片
      form.key = created.id
      form.persistedId = created.id
      form.name = created.name
      form.baseUrl = created.baseUrl
      form.apiKeyConfigured = created.apiKeyConfigured
      // 以落库后的模型目录为准（含 DB ID，可编辑）
      form.models = created.models.length ? created.models : testedModels
    }
    form.apiKey = ''
    form.justSaved = true
    setTimeout(() => (form.justSaved = false), 1800)
  } finally {
    form.saving = false
  }
}

/** 测试连接：调用厂商模型列表接口，成功后用返回目录刷新模型列表 */
async function onTestConnection(form: InstanceForm) {
  const provider = selectedProvider.value
  if (!provider || form.testing) return

  form.testing = true
  form.testOk = null
  form.testMessage = ''
  try {
    const result = await testProviderConnection(projectId, provider.id, {
      providerName: provider.name,
      ...(form.persistedId ? { instanceId: form.persistedId } : {}),
      ...(form.apiKey.trim() ? { apiKey: form.apiKey.trim() } : {}),
      ...(form.baseUrl.trim() ? { baseUrl: form.baseUrl.trim() } : {}),
    })
    // 保留已编辑的类型/上下文长度，其余按厂商目录刷新
    const prevByName = new Map(form.models.map((model) => [model.name, model]))
    const discovered: ProviderModel[] = result.models.map((model) => ({
      id: model.id,
      name: model.name,
      modelType: prevByName.get(model.name)?.modelType ?? model.type ?? null,
      maxContextLength: prevByName.get(model.name)?.maxContextLength ?? null,
    }))
    form.models = discovered
    // 已保存实例：目录同步落库（按名称对齐，保留已编辑字段），并以落库结果为准
    if (form.persistedId) {
      await syncModels(
        projectId,
        provider.id,
        form.persistedId,
        discovered.map((model) => ({ name: model.name, modelType: model.modelType })),
      )
      const instance = provider.instances.find((item) => item.id === form.persistedId)
      if (instance?.models.length) form.models = instance.models
    }
    form.testOk = true
    form.testMessage = result.total
      ? `连接成功，获取到 ${result.total} 个模型`
      : '连接成功，但未获取到模型'
  } catch (error) {
    form.testOk = false
    form.testMessage = error instanceof Error ? error.message : '连接失败，请检查配置'
  } finally {
    form.testing = false
  }
}

/** ---------------- 模型类型 / 上下文长度编辑 ---------------- */
/** 模型类型选项与展示文案 */
const MODEL_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'chat', label: '对话' },
  { value: 'embedding', label: '嵌入' },
  { value: 'rerank', label: '重排' },
  { value: 'audio', label: '语音' },
  { value: 'moderation', label: '审核' },
]

const MODEL_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  MODEL_TYPE_OPTIONS.map((option) => [option.value, option.label]),
)

/** 上下文长度展示：128000 -> 128K */
function formatContext(length: number): string {
  return length >= 1000 && length % 1000 === 0 ? `${length / 1000}K` : String(length)
}

/** 当前编辑中的模型（卡片 key + 模型 id 唯一标识） */
const editingKey = ref('')
const editType = ref('')
const editContext = ref('')
const savingModel = ref(false)

function startEdit(form: InstanceForm, model: ProviderModel) {
  editingKey.value = `${form.key}:${model.id}`
  editType.value = model.modelType ?? ''
  editContext.value = model.maxContextLength != null ? String(model.maxContextLength) : ''
}

function cancelEdit() {
  editingKey.value = ''
  editType.value = ''
  editContext.value = ''
}

async function saveEdit(form: InstanceForm, model: ProviderModel) {
  if (savingModel.value) return
  const provider = selectedProvider.value
  if (!provider) return

  const modelType = editType.value
  const contextText = editContext.value.trim()
  const maxContextLength = contextText ? Number(contextText) : null
  // 上下文长度须为正整数
  if (maxContextLength !== null && (!Number.isInteger(maxContextLength) || maxContextLength <= 0)) return

  savingModel.value = true
  try {
    if (form.persistedId) {
      await updateModel(projectId, provider.id, form.persistedId, model.id, {
        modelType,
        maxContextLength,
      })
    } else {
      // 草稿实例：仅更新本地状态，保存实例时随目录一并落库
      model.modelType = modelType || null
      model.maxContextLength = maxContextLength
    }
    cancelEdit()
  } finally {
    savingModel.value = false
  }
}
</script>

<template>
  <div class="lg:flex lg:h-full lg:min-h-0 lg:flex-col">
    <!-- 说明：模型配置按项目隔离，实例保存后归属当前项目 -->
    <p class="mb-5 text-xs leading-relaxed text-muted lg:shrink-0">
      模型配置仅对当前项目生效：保存后模型实例关联该项目，其他项目需单独配置。
    </p>

    <!-- 加载骨架 -->
    <div
      v-if="!loaded"
      class="grid gap-5 lg:min-h-0 lg:flex-1 lg:grid-cols-[260px_minmax(0,1fr)]"
    >
      <div class="h-72 animate-pulse rounded-2xl bg-white/5" />
      <div class="h-72 animate-pulse rounded-2xl bg-white/5" />
    </div>

    <div
      v-else
      class="grid items-start gap-5 lg:min-h-0 lg:flex-1 lg:grid-cols-[260px_minmax(0,1fr)] lg:grid-rows-1 lg:items-stretch"
    >
      <!-- 提供商面板：搜索 + 列表（移动端横向滑动；桌面端纵向、列表内部滚动） -->
      <div
        class="lg:flex lg:min-h-0 lg:flex-col lg:rounded-2xl lg:border lg:border-white/6 lg:bg-white/[0.02] lg:p-2"
      >
        <div class="relative">
          <Search
            class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
            aria-hidden="true"
          />
          <input
            v-model="search"
            type="search"
            placeholder="搜索模型提供商…"
            aria-label="搜索模型提供商"
            class="h-9 w-full rounded-lg border border-white/10 bg-input pr-3 pl-9 text-sm text-ink outline-none transition-all duration-200 placeholder:text-muted/70 focus:border-accent focus:shadow-[0_0_0_3px_rgba(94,106,210,0.25)]"
          />
        </div>
        <nav
          v-scroll-auto-hide
          aria-label="模型提供商"
          class="scroll-auto-hide mt-2 flex gap-2 overflow-x-auto pb-1 lg:min-h-0 lg:flex-1 lg:flex-col lg:gap-1 lg:overflow-y-auto lg:pb-0"
        >
          <button
            v-for="p in filteredProviders"
            :key="p.id"
            type="button"
            class="flex shrink-0 items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition-colors lg:w-full"
            :class="
              p.id === selectedProvider?.id
                ? 'bg-white/8 text-ink lg:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]'
                : 'text-muted hover:bg-white/5 hover:text-ink'
            "
            @click="selectProvider(p.id)"
          >
            <!-- 厂商 LOGO：取后端返回的静态资源；未配置 LOGO 时回退首字母图标 -->
            <img
              v-if="p.logo"
              :src="p.logo"
              alt=""
              aria-hidden="true"
              draggable="false"
              class="size-6 shrink-0 object-contain"
            />
            <span
              v-else
              class="flex size-6 shrink-0 items-center justify-center rounded-md text-[11px] font-bold text-white/95"
              :style="{ backgroundColor: p.color }"
            >
              {{ p.name.slice(0, 1) }}
            </span>
            <span class="whitespace-nowrap">{{ p.name }}</span>
            <!-- 仅保留状态点：绿色点亮表示已正常配置，不展示文字描述 -->
            <span
              class="ml-auto size-1.5 shrink-0 rounded-full"
              :class="STATUS_DOT[statusOf(p)]"
              aria-hidden="true"
            />
          </button>
          <EmptyState
            v-if="!filteredProviders.length"
            title="未找到匹配的提供商"
            description="换个关键词试试"
            class="hidden lg:block"
          />
        </nav>
      </div>

      <!-- 右侧：选中提供商的模型实例列表 + 底部添加入口（桌面端独立滚动） -->
      <section
        v-if="selectedProvider"
        v-scroll-auto-hide
        class="scroll-auto-hide min-w-0 space-y-5 lg:min-h-0 lg:overflow-y-auto lg:pr-1"
      >
        <!-- 模型实例卡片：连接配置 + 模型列表同框，每个实例独立保存/删除 -->
        <div
          v-for="card in forms"
          :key="card.key"
          class="rounded-2xl border border-white/6 bg-white/[0.02]"
        >
          <div class="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b border-white/6 px-5 py-3.5">
            <div class="flex min-w-0 flex-1 flex-wrap items-end gap-2">
              <!-- 实例名称与保存/删除同一行，字段样式与 API Key 一致（字段名 + 输入框） -->
              <div class="w-full min-w-0 sm:w-64">
                <label
                  class="block text-xs font-medium text-muted"
                  :for="`instance-name-${card.key}`"
                >
                  实例名称
                </label>
                <AppInput
                  :id="`instance-name-${card.key}`"
                  v-model="card.name"
                  class="mt-1.5"
                  placeholder="例如：生产环境 OpenAI"
                />
              </div>
              <span v-if="card.justSaved" class="mb-2 shrink-0 text-xs text-emerald-300">已保存</span>
              <span
                v-if="card.apiKeyConfigured"
                class="mb-1 inline-flex shrink-0 items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-300"
              >
                <BadgeCheck class="size-3" />
                API Key 已配置
              </span>
            </div>
            <div class="ml-auto flex shrink-0 items-center gap-2">
              <AppButton
                variant="primary"
                size="sm"
                :loading="card.saving"
                :disabled="!card.name.trim()"
                @click="onSave(card)"
              >
                保存
              </AppButton>
              <AppButton variant="danger" size="sm" @click="onDelete(card)">删除</AppButton>
            </div>
          </div>

          <!-- 连接配置 -->
          <div class="px-5 py-4">
            <div class="flex items-center justify-between gap-3">
              <h4 class="text-sm font-semibold">连接配置</h4>
              <AppButton
                variant="secondary"
                size="sm"
                :loading="card.testing"
                @click="onTestConnection(card)"
              >
                <PlugZap class="size-3.5" />
                测试连接
              </AppButton>
            </div>
            <div class="mt-3 space-y-4">
              <div>
                <label
                  class="flex items-center gap-1.5 text-xs font-medium text-muted"
                  :for="`instance-api-key-${card.key}`"
                >
                  <KeyRound class="size-3.5" />
                  API Key
                </label>
                <AppInput
                  :id="`instance-api-key-${card.key}`"
                  v-model="card.apiKey"
                  type="password"
                  class="mt-1.5"
                  autocomplete="off"
                  :placeholder="card.apiKeyConfigured ? '已配置，输入新 Key 可覆盖' : '粘贴提供商控制台生成的 API Key'"
                />
                <p class="mt-1.5 text-xs text-muted/80">Key 由服务端存储，保存后不再回显。</p>
              </div>
              <div>
                <label
                  class="block text-xs font-medium text-muted"
                  :for="`instance-base-url-${card.key}`"
                >
                  API Base URL
                </label>
                <AppInput
                  :id="`instance-base-url-${card.key}`"
                  v-model="card.baseUrl"
                  class="mt-1.5"
                  :placeholder="defaultBaseUrlPlaceholder"
                />
                <p class="mt-1.5 text-xs text-muted/80">
                  留空使用官方默认地址；如需经代理或私有网关接入，可填写自定义接入点。
                </p>
              </div>
            </div>
            <p
              v-if="card.testMessage"
              class="mt-3 text-xs"
              :class="card.testOk ? 'text-emerald-300' : 'text-red-300'"
            >
              {{ card.testMessage }}
            </p>
          </div>

          <!-- 模型列表 -->
          <div class="border-t border-white/6">
            <div class="px-5 py-3.5">
              <h4 class="text-sm font-semibold">模型列表</h4>
              <p class="mt-0.5 text-xs text-muted">
                模型类型与最大上下文长度可编辑补充，未设置时不展示。
              </p>
            </div>
            <ul v-if="card.models.length" class="divide-y divide-white/6">
              <li
                v-for="m in card.models"
                :key="m.id"
                class="px-5 py-3.5"
              >
                <!-- 展示态 -->
                <div
                  v-if="editingKey !== `${card.key}:${m.id}`"
                  class="flex items-center justify-between gap-4"
                >
                  <div class="min-w-0">
                    <p class="truncate text-sm font-medium">{{ m.name }}</p>
                    <div
                      v-if="m.modelType || m.maxContextLength != null"
                      class="mt-1 flex flex-wrap items-center gap-1.5"
                    >
                      <span
                        v-if="m.modelType"
                        class="rounded-full bg-white/8 px-2 py-0.5 text-[11px] text-muted"
                      >
                        {{ MODEL_TYPE_LABELS[m.modelType] ?? m.modelType }}
                      </span>
                      <span
                        v-if="m.maxContextLength != null"
                        class="rounded-full bg-white/8 px-2 py-0.5 text-[11px] text-muted"
                      >
                        上下文 {{ formatContext(m.maxContextLength) }}
                      </span>
                    </div>
                  </div>
                  <AppButton
                    variant="ghost"
                    size="sm"
                    :aria-label="`编辑模型 ${m.name}`"
                    @click="startEdit(card, m)"
                  >
                    <Pencil class="size-3.5" />
                    编辑
                  </AppButton>
                </div>

                <!-- 编辑态 -->
                <div v-else class="space-y-3">
                  <div class="grid gap-3 sm:grid-cols-2">
                    <div class="space-y-1.5">
                      <label class="text-xs font-medium text-muted" :for="`model-type-${card.key}-${m.id}`">
                        模型类型
                      </label>
                      <AppSelect
                        :id="`model-type-${card.key}-${m.id}`"
                        v-model="editType"
                        :options="MODEL_TYPE_OPTIONS"
                        placeholder="不设置"
                      />
                    </div>
                    <div class="space-y-1.5">
                      <label
                        class="block text-xs font-medium text-muted"
                        :for="`model-context-${card.key}-${m.id}`"
                      >
                        最大上下文长度
                      </label>
                      <AppInput
                        :id="`model-context-${card.key}-${m.id}`"
                        v-model="editContext"
                        type="number"
                        min="1"
                        placeholder="如 128000，留空不展示"
                      />
                    </div>
                  </div>
                  <div class="flex justify-end gap-2">
                    <AppButton variant="ghost" size="sm" @click="cancelEdit">取消</AppButton>
                    <AppButton variant="primary" size="sm" :loading="savingModel" @click="saveEdit(card, m)">
                      保存
                    </AppButton>
                  </div>
                </div>
              </li>
            </ul>
            <p v-else class="px-5 pb-4 text-xs text-muted">
              点击「测试连接」可获取该实例的模型目录。
            </p>
          </div>
        </div>

        <!-- 无实例时的空状态 -->
        <EmptyState
          v-if="!forms.length"
          title="暂无模型实例"
          description="点击下方“添加模型实例”，为该提供商配置连接信息与模型。"
        />

        <!-- 添加模型实例：始终位于实例列表底部 -->
        <div class="flex justify-center pt-1">
          <AppButton variant="primary" class="min-w-52" @click="addInstance">
            <Plus class="size-4" />
            添加模型实例
          </AppButton>
        </div>
      </section>
    </div>

    <!-- 删除已保存实例前的确认 -->
    <ConfirmModal
      :open="!!pendingDelete"
      title="删除模型实例"
      :description="`删除后该实例的连接配置与模型配置将一并清除，确定删除“${pendingDelete?.name ?? ''}”吗？`"
      confirm-text="删除"
      danger
      :loading="deleting"
      @close="pendingDelete = null"
      @confirm="confirmDelete"
    />
  </div>
</template>
