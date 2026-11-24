/**
 * 模型配置领域模型
 * 提供商目录 + 项目内模型实例（同一提供商可创建多个实例）。
 */

/** 提供商所属区域：global 国际 / china 国内 */
export type ProviderRegion = 'global' | 'china'

/** 实例下的可选模型 */
export interface ProviderModel {
  id: string
  /** 模型名称（厂商模型 ID） */
  name: string
  /** 模型类型：chat / embedding / rerank...（未填写为 null，不展示） */
  modelType: string | null
  /** 最大上下文长度（未填写为 null，不展示） */
  maxContextLength: number | null
}

/** 模型目录同步项（测试连接结果写入实例） */
export interface ProviderModelSeed {
  name: string
  modelType?: string | null
}

/** 项目内的模型实例（连接配置按实例保存） */
export interface ProviderInstance {
  id: string
  /** 实例名称 */
  name: string
  /** 当前配置的 API Base URL；空串表示未自定义，使用提供商默认地址 */
  baseUrl: string
  /** 是否已配置 API Key（出于安全考虑，后端不回传明文，仅回传该标记） */
  apiKeyConfigured: boolean
  /** 是否启用该实例 */
  enabled: boolean
  models: ProviderModel[]
}

/** 模型提供商 */
export interface ModelProvider {
  id: string
  name: string
  region: ProviderRegion
  /** 品牌色（无 LOGO 时的回退头像底色，前端展示用） */
  color: string
  /** 厂商 LOGO 静态资源路径（如 /provider-logos/openai.svg；空串时回退首字母图标） */
  logo: string
  /** 官方默认 API Base URL（实例未自定义时使用，前端仅作占位提示） */
  defaultBaseUrl: string
  /** 任一实例已配置 API Key 时为 true */
  apiKeyConfigured: boolean
  /** 该项目下该提供商的模型实例列表 */
  instances: ProviderInstance[]
}

/** 项目内可选嵌入模型（知识库创建时选择向量模型） */
export interface EmbeddingModelOption {
  /** 模型记录 ID（前端下拉框选中标识） */
  id: string
  /** 嵌入模型名称（知识库 embed_model 存储值） */
  name: string
  /** 下拉框展示文案：实例名/嵌入模型 */
  label: string
  instanceId: string
  instanceName: string
  providerId: string
  providerName: string
}

/** 项目内可选LLM（文件处理策略数据提取器选择模型），结构与嵌入模型选项一致 */
export type ChatModelOption = EmbeddingModelOption

/** 厂商模型目录中的一项（测试连接返回） */
export interface DiscoveredProviderModel {
  /** 模型 ID（如 gpt-4o、bge-m3） */
  id: string
  /** 展示名称（部分厂商回传 display_name，缺省与 ID 相同） */
  name: string
  /** 模型类型：chat / embedding / rerank / audio / moderation */
  type: string
}

/** 测试连接结果 */
export interface ProviderConnectionTestResult {
  provider: string
  /** 实际请求使用的 API Base URL */
  baseUrl: string
  models: DiscoveredProviderModel[]
  total: number
}

/** 测试模型连接载荷 */
export interface ProviderConnectionTestPatch {
  /** 提供商名称，用于匹配后端预置目录与鉴权协议 */
  providerName: string
  /** 已保存的实例 ID；草稿实例不传 */
  instanceId?: string
  /** 临时测试用 API Key，缺省回退到已保存配置 */
  apiKey?: string
  /** 临时测试用 API Base URL，缺省回退到实例配置或厂商默认地址 */
  baseUrl?: string
}

/** 新建模型实例载荷 */
export interface ProviderInstanceCreatePatch {
  name: string
  apiKey?: string
  baseUrl?: string
  /** 随实例保存的模型目录（测试连接结果） */
  models?: ProviderModelSeed[]
}

/** 模型目录同步载荷（按名称全量对齐） */
export interface ProviderModelSyncPatch {
  models: ProviderModelSeed[]
}

/** 编辑模型载荷：未传字段表示不修改；modelType 空串 / maxContextLength null 表示清除 */
export interface ProviderModelUpdatePatch {
  modelType?: string | null
  maxContextLength?: number | null
}

/** 保存模型实例配置载荷 */
export interface ProviderInstanceUpdatePatch {
  name?: string
  apiKey?: string
  baseUrl?: string
  enabled?: boolean
}
