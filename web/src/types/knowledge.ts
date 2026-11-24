/**
 * 知识库领域模型
 * TODO(backend): 以下字段为前端先行约定，后端就绪后以实际返回为准，联调时统一调整。
 */

/** 文件索引状态（failed 为后端扩展：解析失败，error 字段带原因） */
export type FileStatus = 'processing' | 'indexed' | 'failed'

/** 知识库 */
export interface KnowledgeBase {
  id: string
  name: string
  description: string
  /** 所属项目（团队级知识库无项目归属） */
  projectId?: string
  /** 所属团队（知识库详情接口附带，用于返回项目页） */
  teamId?: string
  /** 向量模型 */
  embedModel?: string
  /** 文件总数 */
  fileCount: number
  /** 分块总数 */
  chunkCount: number
  /** 创建时间（ISO 8601） */
  createdAt: string
  /** 最近更新时间（ISO 8601） */
  updatedAt: string
  /** 项目内自定义排序值（越小越靠前） */
  sortOrder?: number
}

/** 知识库内文件 */
export interface KnowledgeFile {
  id: string
  kbId: string
  /** 文件名（含扩展名） */
  name: string
  /** 文件大小（字节） */
  size: number
  /** 分块数量 */
  chunkCount: number
  status: FileStatus
  /** 处理该文件所使用的策略 ID（未指定策略时为空） */
  strategyId?: string
  /** 策略名称（文件列表展示用，策略已被删除时为空） */
  strategyName?: string | null
  /** MIME 类型 */
  contentType?: string
  /** 解析失败原因（仅 status=failed 时有值） */
  error?: string
  /** 创建时间（ISO 8601） */
  createdAt?: string
  updatedAt: string
}

/** 文件解析器 */
export type FileParser = 'Docling' | 'MonkeyOCRv2'

/** 文件分块器 */
export type ChunkStrategy =
  | 'semantic'
  | 'sentence'
  | 'sentence_window'
  | 'hierarchical'
  | 'markdown'
  | 'html'
  | 'json'
  | 'code'
  | 'token'
  | 'simple_file'

/** 数据提取器 */
export type DataExtractor =
  | 'title'
  | 'question'
  | 'entity'
  | 'summary'
  | 'keyword'
  | 'none'

/** 编排序列中的提取器节点（每个实例独立指定执行LLM，空串表示该提取器跳过） */
export interface StageExtractorEntry {
  id: Exclude<DataExtractor, 'none'>
  llm: string
  /** 提取器参数配置（未提供的键按后端默认值生效） */
  params: Record<string, number | string>
}

/** 编排序列中的分块器节点（params 为分块器参数配置，未提供的键按后端默认值生效） */
export interface SplitStageEntry {
  id: ChunkStrategy
  params: Record<string, number | string>
}

/**
 * 策略编排序列：解析 → 前置(文档级)提取 → 分块(可级联) → 后置(块级)提取。
 * parser 至多1个，split 至少1个；执行顺序即 transformations 顺序。
 */
export interface StrategyStages {
  parser: FileParser[]
  pre_extract: StageExtractorEntry[]
  /** 分块器序列（兼容历史数据可能出现纯字符串 id，展示/编辑前先经 normalizeSplitEntries 归一化） */
  split: SplitStageEntry[]
  post_extract: StageExtractorEntry[]
}

/** 图谱schema实体类型：属性字段为「属性名→属性描述」映射 */
export interface GraphSchemaEntity {
  name: string
  desc: string
  properties: Record<string, string>
}

/** 图谱schema关系类型（subject/object 须指向 entities 中的实体类型） */
export interface GraphSchemaRelation {
  name: string
  desc: string
  subjectType: string
  objectType: string
}

/** 知识库图谱schema（每库一份；构图抽取的实体/关系对齐依据，策略开启构建图谱时引用） */
export interface GraphSchema {
  kbId: string
  entities: GraphSchemaEntity[]
  relations: GraphSchemaRelation[]
  createdAt: string
  updatedAt: string
}

/**
 * 文件处理策略（知识库维度，可创建多条并被文档引用）
 */
export interface FileParseStrategy {
  id: string
  /** 所属知识库 */
  kbId: string
  /** 策略名称 */
  name: string
  /** 嵌入模型（项目模型实例下的 embedding 模型名） */
  embedModel: string
  /** 编排序列：解析 → 前置提取 → 分块 → 后置提取（提取器条目各自携带执行LLM） */
  stages: StrategyStages
  /** 是否构建知识图谱（开启时要求知识库已创建图谱schema，schema在「图谱schema」页签维护） */
  graph: boolean
  /** 引用该策略的文档数（后端聚合，用于修改/删除校验） */
  documentCount: number
  createdAt: string
  updatedAt: string
}

/** 新建/修改策略的可编辑字段（编排序列优先，单值字段由后端派生） */
export type FileParseStrategyPatch = Pick<
  FileParseStrategy,
  'name' | 'embedModel' | 'graph'
> & {
  stages: StrategyStages
}

/** 文件分块 */
export interface Chunk {
  id: string
  fileId: string
  /** 分块序号（从 1 开始） */
  index: number
  /** 分块正文 */
  content: string
  /** Token 估算值 */
  tokens: number
  /**
   * 元数据键值对。
   * TODO(backend): 若后端支持数组/数值等复杂类型，联调时扩展此结构。
   */
  metadata: Record<string, string>
  updatedAt: string
}
