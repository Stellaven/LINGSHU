/**
 * 项目内模型配置模块 API 层
 * ------------------------------------------------------------------
 * 已接后端（鉴权经统一拦截器，request 自动携带AT并处理40102静默刷新）：
 *   GET    /api/projects/{projectId}/providers/list                                      项目内提供商目录（含模型实例）
 *   GET    /api/projects/{projectId}/providers/embedding-models                          项目内可选嵌入模型
 *   POST   /api/projects/{projectId}/providers/{providerId}/test-connection              测试连接并获取模型列表
 *   POST   /api/projects/{projectId}/providers/{providerId}/instances                    新建模型实例 body: { name, api_key?, base_url?, models? }
 *   PUT    /api/projects/{projectId}/providers/{providerId}/instances/{instanceId}/models        同步实例模型目录 body: { models: [{ name, model_type? }] }
 *   PATCH  /api/projects/{projectId}/providers/{providerId}/instances/{instanceId}/models/{modelId}  编辑模型 body: { model_type?, max_context_length? }
 *   PATCH  /api/projects/{projectId}/providers/{providerId}/instances/{instanceId}/update  保存实例配置 body: { name?, api_key?, base_url?, enabled? }
 *   DELETE /api/projects/{projectId}/providers/{providerId}/instances/{instanceId}/delete  删除模型实例
 *
 * 安全约定：API Key 仅在保存时上传；所有查询接口只回传 apiKeyConfigured 标记，不回传明文。
 */

import { request } from './http'
import type {
  ChatModelOption,
  EmbeddingModelOption,
  ModelProvider,
  ProviderConnectionTestPatch,
  ProviderConnectionTestResult,
  ProviderInstance,
  ProviderInstanceCreatePatch,
  ProviderInstanceUpdatePatch,
  ProviderModel,
  ProviderModelSyncPatch,
  ProviderModelUpdatePatch,
} from '@/types/models'

/** GET /api/projects/{projectId}/providers/list */
export async function listProviders(projectId: string): Promise<ModelProvider[]> {
  return request<ModelProvider[]>(`/projects/${projectId}/providers/list`)
}

/** GET /api/projects/{projectId}/providers/embedding-models */
export async function listEmbeddingModels(projectId: string): Promise<EmbeddingModelOption[]> {
  return request<EmbeddingModelOption[]>(`/projects/${projectId}/providers/embedding-models`)
}

/** GET /api/projects/{projectId}/providers/chat-models */
export async function listChatModels(projectId: string): Promise<ChatModelOption[]> {
  return request<ChatModelOption[]>(`/projects/${projectId}/providers/chat-models`)
}

/**
 * POST /api/projects/{projectId}/providers/{providerId}/test-connection
 * 不校验提供商/实例存在性（初次添加实例时数据库尚无记录）；
 * 未传 apiKey/baseUrl 时后端回退到已保存实例配置或厂商默认地址。
 */
export async function testProviderConnection(
  projectId: string,
  providerId: string,
  patch: ProviderConnectionTestPatch,
): Promise<ProviderConnectionTestResult> {
  return request<ProviderConnectionTestResult>(
    `/projects/${projectId}/providers/${providerId}/test-connection`,
    {
      method: 'POST',
      body: {
        provider_name: patch.providerName,
        ...(patch.instanceId !== undefined ? { instance_id: Number(patch.instanceId) } : {}),
        ...(patch.apiKey !== undefined ? { api_key: patch.apiKey } : {}),
        ...(patch.baseUrl !== undefined ? { base_url: patch.baseUrl } : {}),
      },
    },
  )
}

/** POST /api/projects/{projectId}/providers/{providerId}/instances */
export async function createProviderInstance(
  projectId: string,
  providerId: string,
  patch: ProviderInstanceCreatePatch,
): Promise<ProviderInstance> {
  return request<ProviderInstance>(`/projects/${projectId}/providers/${providerId}/instances`, {
    method: 'POST',
    body: {
      name: patch.name,
      ...(patch.apiKey !== undefined ? { api_key: patch.apiKey } : {}),
      ...(patch.baseUrl !== undefined ? { base_url: patch.baseUrl } : {}),
      ...(patch.models
        ? { models: patch.models.map((model) => ({ name: model.name, model_type: model.modelType ?? null })) }
        : {}),
    },
  })
}

/**
 * PATCH /api/projects/{projectId}/providers/{providerId}/instances/{instanceId}/update
 * apiKey 传空字符串表示清除已配置的 Key；baseUrl 传空字符串表示恢复使用默认地址。
 */
export async function updateProviderInstance(
  projectId: string,
  providerId: string,
  instanceId: string,
  patch: ProviderInstanceUpdatePatch,
): Promise<ProviderInstance> {
  return request<ProviderInstance>(
    `/projects/${projectId}/providers/${providerId}/instances/${instanceId}/update`,
    {
      method: 'PATCH',
      body: {
        ...(patch.name !== undefined ? { name: patch.name } : {}),
        ...(patch.apiKey !== undefined ? { api_key: patch.apiKey } : {}),
        ...(patch.baseUrl !== undefined ? { base_url: patch.baseUrl } : {}),
        ...(patch.enabled !== undefined ? { enabled: patch.enabled } : {}),
      },
    },
  )
}

/** DELETE /api/projects/{projectId}/providers/{providerId}/instances/{instanceId}/delete */
export async function deleteProviderInstance(
  projectId: string,
  providerId: string,
  instanceId: string,
): Promise<void> {
  await request<{ id: string }>(
    `/projects/${projectId}/providers/${providerId}/instances/${instanceId}/delete`,
    { method: 'DELETE' },
  )
}

/** 模型目录同步结果 */
export interface InstanceModelsSyncResult {
  id: string
  models: ProviderModel[]
}

/**
 * PUT /api/projects/{projectId}/providers/{providerId}/instances/{instanceId}/models
 * 按名称全量对齐模型目录：新增缺失、移除多余，保留已编辑的类型/上下文。
 */
export async function syncInstanceModels(
  projectId: string,
  providerId: string,
  instanceId: string,
  patch: ProviderModelSyncPatch,
): Promise<InstanceModelsSyncResult> {
  return request<ProviderInstance>(
    `/projects/${projectId}/providers/${providerId}/instances/${instanceId}/models`,
    {
      method: 'PUT',
      body: {
        models: patch.models.map((model) => ({ name: model.name, model_type: model.modelType ?? null })),
      },
    },
  )
}

/**
 * PATCH /api/projects/{projectId}/providers/{providerId}/instances/{instanceId}/models/{modelId}
 * 编辑模型类型与最大上下文长度。
 */
export async function updateProviderModel(
  projectId: string,
  providerId: string,
  instanceId: string,
  modelId: string,
  patch: ProviderModelUpdatePatch,
): Promise<void> {
  await request(
    `/projects/${projectId}/providers/${providerId}/instances/${instanceId}/models/${modelId}`,
    {
      method: 'PATCH',
      body: {
        ...(patch.modelType !== undefined ? { model_type: patch.modelType } : {}),
        ...(patch.maxContextLength !== undefined
          ? { max_context_length: patch.maxContextLength }
          : {}),
      },
    },
  )
}
