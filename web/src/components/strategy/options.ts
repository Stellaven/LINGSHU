/**
 * 文件处理策略可选项目录
 * ------------------------------------------------------------------
 * 列表展示、详情查看与新建/修改表单共用同一份选项定义，
 * 保证展示文案与图标随选项调整同步更新。
 */

import {
  Ban,
  Braces,
  Code,
  Files,
  FileText,
  Hash,
  Heading,
  LayoutGrid,
  ListTree,
  MessageCircleQuestionMark,
  Network,
  Pilcrow,
  Rows3,
  ScanText,
  Sparkles,
  Tags,
  TextQuote,
  Type,
} from '@lucide/vue'
import type { Component } from 'vue'
import type {
  ChunkStrategy,
  DataExtractor,
  FileParser,
  FileParseStrategyPatch,
  SplitStageEntry,
  StrategyStages,
} from '@/types/knowledge'

export interface StrategyOption<T extends string> {
  value: T
  name: string
  description: string
  icon: Component
  /** 名称使用等宽字体（解析器/模型标识等英文名称） */
  monospace?: boolean
}

export const PARSERS: StrategyOption<FileParser>[] = [
  {
    value: 'Docling',
    name: 'Docling',
    description: '通用文档解析，覆盖 PDF、Word、PPT 等格式',
    icon: FileText,
    monospace: true,
  },
]

export const CHUNKERS: StrategyOption<ChunkStrategy>[] = [
  {
    value: 'semantic',
    name: '语义分块',
    description: '按语义相似度聚合段落，分块更连贯',
    icon: Sparkles,
  },
  {
    value: 'sentence',
    name: '句子分块',
    description: '按句子边界切分，粒度均匀',
    icon: Pilcrow,
  },
  {
    value: 'token',
    name: 'Token 分块',
    description: '按固定 token 数量切分，块大小精确可控',
    icon: Hash,
  },
  {
    value: 'sentence_window',
    name: '句子窗口',
    description: '句子级分块并保留上下文窗口',
    icon: Rows3,
  },
  {
    value: 'hierarchical',
    name: '层级分块',
    description: '父子分块，兼顾概览检索与细节回溯',
    icon: ListTree,
  },
  {
    value: 'markdown',
    name: 'Markdown 分块',
    description: '按标题层级切分并保留文档结构',
    icon: Heading,
  },
  {
    value: 'html',
    name: 'HTML 分块',
    description: '按标签层级切分并保留页面结构',
    icon: LayoutGrid,
  },
  {
    value: 'json',
    name: 'JSON 分块',
    description: '按键路径切分并保留数据层级',
    icon: Braces,
  },
  {
    value: 'code',
    name: '代码分块',
    description: '按语言语法结构切分，保留代码完整性',
    icon: Code,
  },
  {
    value: 'simple_file',
    name: '简单文件分块',
    description: '按文件后缀自动选择结构化分块，其他类型整文成块',
    icon: Files,
  },
]

export const EXTRACTORS: StrategyOption<DataExtractor>[] = [
  {
    value: 'title',
    name: '标题提取',
    description: '推断并提取文档标题，写入块元数据',
    icon: Type,
  },
  {
    value: 'summary',
    name: '文档摘要',
    description: '概括块内容生成摘要，写入块元数据',
    icon: TextQuote,
  },
  {
    value: 'question',
    name: '问题提取',
    description: '生成每个块可回答的问题，提升问答检索命中',
    icon: MessageCircleQuestionMark,
  },
  {
    value: 'keyword',
    name: '关键词提取',
    description: '提取块中的关键词，辅助检索召回',
    icon: Tags,
  },
  {
    value: 'entity',
    name: '实体抽取',
    description: '抽取人名、组织、地点等实体写入块元数据',
    icon: Network,
  },
  {
    value: 'none',
    name: '不提取',
    description: '仅保留解析后的文本内容，不额外抽取数据',
    icon: Ban,
  },
]

/**
 * 新建策略时的默认编排（解析器与分块器预置，提取器默认留空即「不提取」；
 * 嵌入模型由项目内已配置的模型决定，默认为空待选中）
 */
export const DEFAULT_STAGES: StrategyStages = {
  parser: ['Docling'],
  pre_extract: [],
  split: [{ id: 'semantic', params: {} }],
  post_extract: [],
}

/** 新建策略时的默认配置 */
export const DEFAULT_STRATEGY_PATCH: FileParseStrategyPatch = {
  name: '',
  embedModel: '',
  graph: true,
  stages: structuredClone(DEFAULT_STAGES),
}

/** 按 value 查找选项（用于列表与详情展示名称） */
export function findOption<T extends string>(
  options: StrategyOption<T>[],
  value: T,
): StrategyOption<T> {
  return options.find((opt) => opt.value === value) ?? options[0]
}

/* ============================================================
 * 编排器（Orchestrator）目录：组件库 / 泳道 / 展示时间线共用
 * ============================================================ */

/** 编排组件类型（与泳道分组一一对应） */
export type OrchestratorType = 'parser' | 'splitter' | 'extractor'

/** 编排组件注册项（params 为后端实际生效的固定配置，仅作展示） */
export interface OrchestratorComponent {
  id: string
  name: string
  description: string
  icon: Component
  /** 参数预览：键值对列表（点击卡片展开） */
  params: [string, string][]
}

/** 编排器组件目录（组件能力与解析管线一一对应） */
export const ORCHESTRATOR_COMPONENTS: Record<OrchestratorType, OrchestratorComponent[]> = {
  parser: [
    {
      id: 'Docling',
      name: 'Docling',
      description: '通用文档解析，覆盖 PDF、Word、PPT 等格式',
      icon: FileText,
      params: [
        ['解析引擎', 'docling-serve'],
        ['输出', 'Markdown'],
      ],
    },
    {
      id: 'MonkeyOCRv2',
      name: 'MonkeyOCRv2',
      description: '复杂版面与扫描件的高精度 OCR 解析',
      icon: ScanText,
      params: [
        ['OCR', '版面识别'],
        ['输出', 'Markdown'],
      ],
    },
  ],
  splitter: [
    {
      id: 'semantic',
      name: '语义分块',
      description: '按语义相似度聚合段落，分块更连贯',
      icon: Sparkles,
      params: [
        ['断点阈值', '95%'],
        ['缓冲窗口', '1 句'],
      ],
    },
    {
      id: 'sentence',
      name: '句子分块',
      description: '按句子边界切分，粒度均匀',
      icon: Pilcrow,
      params: [
        ['块大小', '200'],
        ['重叠', '50'],
      ],
    },
    {
      id: 'token',
      name: 'Token 分块',
      description: '按固定 token 数量切分，块大小精确可控',
      icon: Hash,
      params: [
        ['块大小', '512 token'],
        ['重叠', '50 token'],
      ],
    },
    {
      id: 'sentence_window',
      name: '句子窗口',
      description: '句子级分块并保留上下文窗口',
      icon: Rows3,
      params: [
        ['窗口大小', '3 句'],
      ],
    },
    {
      id: 'hierarchical',
      name: '层级分块',
      description: '父子分块，兼顾概览检索与细节回溯',
      icon: ListTree,
      params: [
        ['层级块长', '1024 / 512 / 256'],
      ],
    },
    {
      id: 'markdown',
      name: 'Markdown 分块',
      description: '按标题层级切分并保留文档结构',
      icon: Heading,
      params: [
        ['切分依据', '标题层级'],
        ['保留标题路径', '是'],
      ],
    },
    {
      id: 'html',
      name: 'HTML 分块',
      description: '按标签层级切分并保留页面结构',
      icon: LayoutGrid,
      params: [
        ['切分依据', '标签层级'],
      ],
    },
    {
      id: 'json',
      name: 'JSON 分块',
      description: '按键路径切分并保留数据层级',
      icon: Braces,
      params: [
        ['切分依据', '键路径'],
      ],
    },
    {
      id: 'code',
      name: '代码分块',
      description: '按语言语法结构切分，保留代码完整性',
      icon: Code,
      params: [
        ['语言', '按文件后缀自动'],
        ['AST', '开启'],
      ],
    },
    {
      id: 'simple_file',
      name: '简单文件分块',
      description: '按文件后缀自动选择结构化分块，其他类型整文成块',
      icon: Files,
      params: [
        ['切分依据', '文件后缀自动'],
        ['结构化类型', 'md / html / json'],
        ['未识别类型', '整文成块'],
      ],
    },
  ],
  extractor: [
    {
      id: 'title',
      name: '标题提取',
      description: '推断并提取文档标题，写入块元数据',
      icon: Type,
      params: [
        ['提取字段', 'document_title'],
        ['执行LLM', '每实例独立配置'],
      ],
    },
    {
      id: 'summary',
      name: '文档摘要',
      description: '概括块内容生成摘要，写入块元数据',
      icon: TextQuote,
      params: [
        ['提取字段', 'section_summary'],
        ['执行LLM', '每实例独立配置'],
      ],
    },
    {
      id: 'question',
      name: '问题提取',
      description: '生成每个块可回答的问题，提升问答检索命中',
      icon: MessageCircleQuestionMark,
      params: [
        ['提取字段', 'questions_this_excerpt_can_answer'],
        ['执行LLM', '每实例独立配置'],
      ],
    },
    {
      id: 'keyword',
      name: '关键词提取',
      description: '提取块中的关键词，辅助检索召回',
      icon: Tags,
      params: [
        ['提取字段', 'excerpt_keywords'],
        ['执行LLM', '每实例独立配置'],
      ],
    },
    {
      id: 'entity',
      name: '实体抽取',
      description: '抽取人名、组织、地点等实体写入块元数据',
      icon: Network,
      params: [
        ['提取字段', 'extracted_entities'],
        ['执行LLM', '每实例独立配置'],
      ],
    },
  ],
}

/** 编排泳道定义（pre = 分块前的文档级提取，post = 分块后的块级提取） */
export interface OrchestratorLane {
  key: 'parser' | 'pre' | 'split' | 'post'
  type: OrchestratorType
  idx: string
  name: string
}

export const ORCHESTRATOR_LANES: OrchestratorLane[] = [
  { key: 'parser', type: 'parser', idx: '01', name: '解析' },
  { key: 'pre', type: 'extractor', idx: '02', name: '文档级提取' },
  { key: 'split', type: 'splitter', idx: '03', name: '分块' },
  { key: 'post', type: 'extractor', idx: '04', name: '块级提取' },
]

/** 泳道分组展示元数据（色点 / 步骤序号配色，与设计系统一致的功能色） */
export const ORCHESTRATOR_TYPE_META: Record<
  OrchestratorType,
  { label: string; text: string; border: string; bg: string; dot: string; bar: string }
> = {
  parser: {
    label: '解析器',
    text: 'text-emerald-300',
    border: 'border-emerald-400/35',
    bg: 'bg-emerald-400/10',
    dot: 'bg-emerald-400',
    // 沿容器圆角内壁贴合的立体色条（box-shadow inset）
    bar: 'rgba(52, 211, 153, 0.75)',
  },
  splitter: {
    label: '分块器',
    text: 'text-indigo-300',
    border: 'border-indigo-400/35',
    bg: 'bg-indigo-400/10',
    dot: 'bg-indigo-400',
    bar: 'rgba(129, 140, 248, 0.8)',
  },
  extractor: {
    label: '提取器',
    text: 'text-amber-300',
    border: 'border-amber-400/35',
    bg: 'bg-amber-400/10',
    dot: 'bg-amber-400',
    bar: 'rgba(251, 191, 36, 0.75)',
  },
}

/** 编排序列扁平化（按执行顺序），供右侧镜像与详情时间线展示 */
export interface FlatStageStep {
  lane: OrchestratorLane['key']
  type: OrchestratorType
  /** 泳道内序号（0 起） */
  idx: number
  component: OrchestratorComponent
  /** 执行LLM（仅提取器有值） */
  llm: string
  /** 全局执行序号（1 起） */
  seq: number
}

export function flattenStages(stages: StrategyStages): FlatStageStep[] {
  const out: FlatStageStep[] = []
  for (const lane of ORCHESTRATOR_LANES) {
    if (lane.type === 'extractor') {
      const entries = lane.key === 'pre' ? stages.pre_extract : stages.post_extract
      entries.forEach((entry, i) => {
        const component = ORCHESTRATOR_COMPONENTS.extractor.find((c) => c.id === entry.id)
        if (component) {
          out.push({ lane: lane.key, type: lane.type, idx: i, component, llm: entry.llm, seq: 0 })
        }
      })
    } else {
      const ids =
        lane.key === 'parser'
          ? stages.parser
          : normalizeSplitEntries(stages.split).map((entry) => entry.id)
      ids.forEach((id, i) => {
        const component = ORCHESTRATOR_COMPONENTS[lane.type].find((c) => c.id === id)
        if (component) {
          out.push({ lane: lane.key, type: lane.type, idx: i, component, llm: '', seq: 0 })
        }
      })
    }
  }
  out.forEach((step, i) => (step.seq = i + 1))
  return out
}

/* ============================================================
 * 分块器参数配置（依据 LlamaIndex 各分块器初始化参数整理）
 * ============================================================ */

/** 分块器参数字段定义 */
export interface ChunkerParamField {
  /** 后端初始化分块器时读取的参数键名 */
  key: string
  label: string
  type: 'number' | 'text' | 'select'
  /** 缺省值（未配置/留空时后端按此默认值初始化分块器） */
  default: number | string
  min?: number
  max?: number
  step?: number
  /** select 选项 */
  options?: { value: string; label: string }[]
  /** 输入框占位提示 */
  placeholder?: string
  /** 参数含义说明（悬停展示） */
  hint?: string
}

/**
 * 各分块器可配置参数（键名与后端 service._build_node_parser 读取的键一致）：
 *   semantic    → SemanticSplitterNodeParser（buffer_size / breakpoint_percentile_threshold）
 *   sentence    → SentenceSplitter（chunk_size / chunk_overlap / paragraph_separator /
 *                 secondary_chunking_regex；separator/tokenizer 等函数型与内部参数不开放）
 *   token       → TokenTextSplitter（chunk_size / chunk_overlap）
 *   sentence_window → SentenceWindowNodeParser（window_size；metadata key 与窗口检索约定耦合不开放）
 *   hierarchical    → HierarchicalNodeParser（chunk_sizes / chunk_overlap）
 *   markdown    → MarkdownNodeParser（header_path_separator）
 *   html        → HTMLNodeParser（tags，逗号分隔）
 *   code        → CodeSplitter（chunk_lines / chunk_lines_overlap / max_chars / count_mode / max_tokens）
 *   json / simple_file 无可配置参数
 */
export const CHUNKER_PARAM_FIELDS: Record<string, ChunkerParamField[]> = {
  semantic: [
    {
      key: 'buffer_size',
      label: '缓冲窗口',
      type: 'number',
      default: 1,
      min: 1,
      max: 20,
      hint: '语义比较时聚合的句子数：1 为逐句比较，>1 会把相邻句子合并评估',
    },
    {
      key: 'breakpoint_percentile_threshold',
      label: '断点阈值（%）',
      type: 'number',
      default: 95,
      min: 1,
      max: 100,
      hint: '相邻句组余弦不相似度超过该百分位即切分；值越小分块越多、粒度越细',
    },
  ],
  sentence: [
    { key: 'chunk_size', label: '块大小（token）', type: 'number', default: 200, min: 32, max: 8192, hint: '每个块的目标 token 数' },
    { key: 'chunk_overlap', label: '重叠（token）', type: 'number', default: 50, min: 0, hint: '相邻块重叠的 token 数，须小于块大小' },
    {
      key: 'paragraph_separator',
      label: '段落分隔符',
      type: 'text',
      default: '\\n\\n\\n',
      placeholder: '用 \\n 表示换行，如 \\n\\n',
      hint: '段落级切分依据；Docling 输出的 Markdown 段落间通常为两个换行，可改为 \\n\\n 让段落更完整',
    },
    {
      key: 'secondary_chunking_regex',
      label: '句内回退正则',
      type: 'text',
      default: '[^,.;。？！]+[,.;。？！]?|[,.;。？！]',
      hint: '单句仍超长时按该正则（子句/标点边界）回退切分',
    },
  ],
  token: [
    { key: 'chunk_size', label: '块大小（token）', type: 'number', default: 512, min: 32, max: 8192, hint: '每个块的目标 token 数' },
    { key: 'chunk_overlap', label: '重叠（token）', type: 'number', default: 50, min: 0, hint: '相邻块重叠的 token 数，须小于块大小' },
  ],
  sentence_window: [
    {
      key: 'window_size',
      label: '窗口大小（句）',
      type: 'number',
      default: 3,
      min: 1,
      max: 20,
      hint: '每个句子节点在元数据中保留前后各 N 句的上下文窗口',
    },
  ],
  hierarchical: [
    {
      key: 'chunk_sizes',
      label: '层级块长（token）',
      type: 'text',
      default: '1024, 512, 256',
      placeholder: '逗号分隔，如 1024, 512, 256',
      hint: '各层块的 token 数，须逐级递减（根→叶）；供父子检索使用',
    },
    { key: 'chunk_overlap', label: '重叠（token）', type: 'number', default: 20, min: 0, hint: '各层切分时相邻块重叠的 token 数' },
  ],
  markdown: [
    {
      key: 'header_path_separator',
      label: '标题路径分隔符',
      type: 'text',
      default: '/',
      hint: '块元数据中标题路径（如「第1章/第2节」）使用的分隔符',
    },
  ],
  html: [
    {
      key: 'tags',
      label: '提取标签',
      type: 'text',
      default: 'p, h1, h2, h3, h4, h5, h6, li, b, i, u, section',
      placeholder: '逗号分隔，如 p, h1, table',
      hint: '仅从这些 HTML 标签中提取文本内容',
    },
  ],
  code: [
    { key: 'chunk_lines', label: '块行数', type: 'number', default: 40, min: 1, max: 500, hint: '每个块包含的代码行数' },
    { key: 'chunk_lines_overlap', label: '行重叠', type: 'number', default: 15, min: 0, hint: '相邻块重叠的行数，须小于块行数' },
    {
      key: 'count_mode',
      label: '块长计量',
      type: 'select',
      default: 'char',
      options: [
        { value: 'char', label: '字符数' },
        { value: 'token', label: 'token 数' },
      ],
      hint: '块大小上限的计量方式',
    },
    { key: 'max_chars', label: '最大字符数', type: 'number', default: 1500, min: 100, hint: '计量方式为「字符数」时生效' },
    { key: 'max_tokens', label: '最大 token 数', type: 'number', default: 512, min: 64, hint: '计量方式为「token 数」时生效' },
  ],
  // json / simple_file 无可配置参数
}

/**
 * 提取器可配置参数（键名与后端 service._build_extractor_set 读取的键一致）：
 *   title    → TitleExtractor（nodes）
 *   summary  → SummaryExtractor 无可配置参数（summaries 固定 ['self']）
 *   question → QuestionsAnsweredExtractor（questions）
 *   keyword  → KeywordExtractor（keywords）
 *   entity   → EntityExtractor（max_entities，自定义实现）
 * 各提取器的 prompt_template（自定义提示词模板）、num_workers 等不开放
 */
export const EXTRACTOR_PARAM_FIELDS: Record<string, ChunkerParamField[]> = {
  title: [
    {
      key: 'nodes',
      label: '取样节点数',
      type: 'number',
      default: 5,
      min: 1,
      max: 50,
      hint: '取文档前 N 个节点综合推断标题；长文档可增大取样提升准确度',
    },
  ],
  // summary 无可配置参数
  question: [
    {
      key: 'questions',
      label: '每块问题数',
      type: 'number',
      default: 5,
      min: 1,
      max: 20,
      hint: '为每个块生成可回答问题的数量',
    },
  ],
  keyword: [
    {
      key: 'keywords',
      label: '每块关键词数',
      type: 'number',
      default: 5,
      min: 1,
      max: 20,
      hint: '为每个块提取关键词的数量',
    },
  ],
  entity: [
    {
      key: 'max_entities',
      label: '每块实体上限',
      type: 'number',
      default: 20,
      min: 1,
      max: 100,
      hint: '单个块最多抽取的实体数量',
    },
  ],
}

/** 兼容历史数据：split 条目可能是纯字符串 id（旧策略）或 {id, params} 对象 */
export function normalizeSplitEntries(split: unknown): SplitStageEntry[] {
  return (Array.isArray(split) ? split : [])
    .map((entry) => {
      if (typeof entry === 'string') return { id: entry as ChunkStrategy, params: {} }
      return {
        id: entry?.id as ChunkStrategy,
        params: (entry?.params ?? {}) as Record<string, number | string>,
      }
    })
    .filter((entry) => Boolean(entry.id))
}
