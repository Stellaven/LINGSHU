/**
 * 项目内模型配置状态（模块级单例，未引入 Pinia 前的轻量方案）
 * ------------------------------------------------------------------
 * 提供商目录 + 模型实例按项目隔离：进入某项目的模型配置 Tab 时拉取；
 * 切换项目时重置并重新拉取。
 * 新增/保存/删除实例、启停模型后同步维护本地状态。
 */

import { computed, reactive } from 'vue'
import type {
  ModelProvider,
  ProviderInstance,
  ProviderInstanceCreatePatch,
  ProviderInstanceUpdatePatch,
  ProviderModelSeed,
  ProviderModelUpdatePatch,
} from '@/types/models'
import * as modelsApi from '@/api/models'

const state = reactive<{
  /** 当前加载的项目 ID */
  projectId: string | null
  providers: ModelProvider[]
  selectedId: string | null
  loaded: boolean
  loading: boolean
}>({ projectId: null, providers: [], selectedId: null, loaded: false, loading: false })

export const providers = computed(() => state.providers)
export const loaded = computed(() => state.loaded)
export const selectedProvider = computed(
  () => state.providers.find((p) => p.id === state.selectedId) ?? null,
)

/** 是否已配置模型：名下任一实例同步过模型目录 */
function hasModels(p: ModelProvider): boolean {
  return p.instances.some((i) => i.models.length > 0)
}

/** 重排列表：配置了模型的提供商排前，组内保持目录原序（稳定排序） */
function sortProviders(): void {
  const order = new Map(state.providers.map((p, i) => [p.id, i]))
  state.providers.sort(
    (a, b) =>
      Number(hasModels(b)) - Number(hasModels(a)) ||
      (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0),
  )
}

/** 首次进入项目模型配置时拉取该项目的提供商目录（同项目重复调用不重复请求） */
export async function ensureProviders(projectId: string): Promise<void> {
  if (state.projectId !== projectId) {
    state.projectId = projectId
    state.providers = []
    state.selectedId = null
    state.loaded = false
  }
  if (state.loaded || state.loading) return
  state.loading = true
  try {
    state.providers = await modelsApi.listProviders(projectId)
    sortProviders()
    state.loaded = true
    if (!state.selectedId && state.providers.length) state.selectedId = state.providers[0].id
  } finally {
    state.loading = false
  }
}

/** 选中某个提供商 */
export function selectProvider(id: string): void {
  state.selectedId = id
}

function findProvider(providerId: string): ModelProvider | undefined {
  return state.providers.find((p) => p.id === providerId)
}

/** 同步提供商层面的 API Key 聚合标记（任一实例已配置即为 true） */
function syncProviderStatus(providerId: string): void {
  const provider = findProvider(providerId)
  if (!provider) return
  provider.apiKeyConfigured = provider.instances.some((i) => i.apiKeyConfigured)
}

/** 为提供商新建模型实例，成功后写入本地状态并重排列表 */
export async function createInstance(
  projectId: string,
  providerId: string,
  patch: ProviderInstanceCreatePatch,
): Promise<ProviderInstance> {
  const instance = await modelsApi.createProviderInstance(projectId, providerId, patch)
  const provider = findProvider(providerId)
  if (provider) {
    provider.instances.push(instance)
    syncProviderStatus(providerId)
    sortProviders()
  }
  return instance
}

/** 保存模型实例连接配置，成功后用后端返回项更新本地状态 */
export async function saveInstance(
  projectId: string,
  providerId: string,
  instanceId: string,
  patch: ProviderInstanceUpdatePatch,
): Promise<ProviderInstance> {
  const updated = await modelsApi.updateProviderInstance(projectId, providerId, instanceId, patch)
  const provider = findProvider(providerId)
  if (provider) {
    const index = provider.instances.findIndex((i) => i.id === instanceId)
    if (index >= 0) provider.instances[index] = updated
    syncProviderStatus(providerId)
  }
  return updated
}

/** 删除模型实例，成功后从本地状态移除并重排列表 */
export async function removeInstance(
  projectId: string,
  providerId: string,
  instanceId: string,
): Promise<void> {
  await modelsApi.deleteProviderInstance(projectId, providerId, instanceId)
  const provider = findProvider(providerId)
  if (provider) {
    provider.instances = provider.instances.filter((i) => i.id !== instanceId)
    syncProviderStatus(providerId)
    sortProviders()
  }
}

/** 同步实例模型目录（测试连接成功后调用），成功后更新本地状态并重排列表 */
export async function syncModels(
  projectId: string,
  providerId: string,
  instanceId: string,
  models: ProviderModelSeed[],
): Promise<void> {
  const result = await modelsApi.syncInstanceModels(projectId, providerId, instanceId, { models })
  const instance = findProvider(providerId)?.instances.find((i) => i.id === instanceId)
  if (instance) instance.models = result.models
  sortProviders()
}

/** 编辑模型类型与最大上下文长度，成功后更新本地状态 */
export async function updateModel(
  projectId: string,
  providerId: string,
  instanceId: string,
  modelId: string,
  patch: ProviderModelUpdatePatch,
): Promise<void> {
  await modelsApi.updateProviderModel(projectId, providerId, instanceId, modelId, patch)
  const model = findProvider(providerId)
    ?.instances.find((i) => i.id === instanceId)
    ?.models.find((m) => m.id === modelId)
  if (!model) return
  if (patch.modelType !== undefined) {
    model.modelType = patch.modelType === '' ? null : patch.modelType
  }
  if (patch.maxContextLength !== undefined) {
    model.maxContextLength = patch.maxContextLength
  }
}
