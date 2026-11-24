/**
 * 临时内存 Mock 数据仓库
 * ------------------------------------------------------------------
 * ⚠️ 该文件为后端未就绪期间的临时方案：所有数据保存在内存中，
 *    刷新页面即恢复初始数据。
 * TODO(backend): 后端联调完成后，删除本文件及 api 层中的 mock 实现。
 */

import type { Chunk, FileParseStrategy, KnowledgeBase, KnowledgeFile } from '@/types/knowledge'
import type { ProjectMember, Team, TeamMember, TeamProject } from '@/types/team'

/** 策略存储记录：文档引用数由 files 实时聚合，不单独落库 */
export type StrategyRecord = Omit<FileParseStrategy, 'documentCount'>

export interface Db {
  teams: Team[]
  teamMembers: TeamMember[]
  teamProjects: TeamProject[]
  projectMembers: ProjectMember[]
  knowledgeBases: KnowledgeBase[]
  files: KnowledgeFile[]
  chunks: Chunk[]
  /** 知识库维度的文件处理策略（kbId 归属，可被多条文件引用） */
  parseStrategies: StrategyRecord[]
}

let seq = 100
export function genId(prefix: string): string {
  seq += 1
  return `${prefix}-${seq}`
}

/**
 * 上传文件的原始内容（fileId → File/Blob），供下载接口返回原文件。
 * ⚠️ 仅存内存：预置 seed 文件不在其中（下载时由 api 层以分块文本合成），刷新页面即失效。
 */
export const blobStore = new Map<string, Blob>()

export const db: Db = {
  teams: [
    {
      id: 'team-1',
      name: '个人',
      description: '我的个人空间，存放个人项目与草稿。',
      createdAt: '2026-10-01T10:00:00+08:00',
    },
    {
      id: 'team-2',
      name: '搜索与推荐组',
      description: '搜索与推荐算法团队的协作空间，沉淀检索与排序相关项目。',
      createdAt: '2026-10-06T14:00:00+08:00',
    },
  ],

  // 预置团队成员（演示账号 demo 预置为 team-1 所有者、team-2 成员；
  // 其他账号列表接口不做自动加入，未加入任何团队时首页显示「当前没有团队」空状态；
  // 直接访问具体团队页时仍按 ensureMembership 语义自动加入）
  teamMembers: [
    { id: 'm-15', teamId: 'team-1', account: 'demo', nickname: 'demo', email: 'demo@example.com', role: 'owner', joinedAt: '2026-10-03T09:00:00+08:00' },
    { id: 'm-13', teamId: 'team-1', account: 'lin.xiao', nickname: '林晓', email: 'lin.xiao@example.com', role: 'member', joinedAt: '2026-10-03T09:30:00+08:00' },
    { id: 'm-14', teamId: 'team-1', account: 'su.mo', nickname: '苏默', email: 'su.mo@example.com', role: 'member', joinedAt: '2026-10-05T15:10:00+08:00' },
    { id: 'm-1', teamId: 'team-2', account: 'zhang.san', nickname: '张三', email: 'zhang.san@example.com', role: 'owner', joinedAt: '2026-10-06T14:00:00+08:00' },
    { id: 'm-2', teamId: 'team-2', account: 'li.si', nickname: '李四', email: 'li.si@example.com', role: 'member', joinedAt: '2026-10-07T09:12:00+08:00' },
    { id: 'm-3', teamId: 'team-2', account: 'wang.wu', nickname: '王五', email: 'wang.wu@example.com', role: 'member', joinedAt: '2026-10-07T15:40:00+08:00' },
    { id: 'm-4', teamId: 'team-2', account: 'zhao.liu', nickname: '赵六', email: 'zhao.liu@example.com', role: 'member', joinedAt: '2026-10-09T10:05:00+08:00' },
    { id: 'm-5', teamId: 'team-2', account: 'chen.qi', nickname: '陈七', email: 'chen.qi@example.com', role: 'member', joinedAt: '2026-10-10T11:30:00+08:00' },
    { id: 'm-6', teamId: 'team-2', account: 'zhou.ba', nickname: '周八', email: 'zhou.ba@example.com', role: 'member', joinedAt: '2026-10-11T14:22:00+08:00' },
    { id: 'm-7', teamId: 'team-2', account: 'wu.jiu', nickname: '吴九', email: 'wu.jiu@example.com', role: 'member', joinedAt: '2026-10-12T09:48:00+08:00' },
    { id: 'm-8', teamId: 'team-2', account: 'zheng.shi', nickname: '郑十', email: 'zheng.shi@example.com', role: 'member', joinedAt: '2026-10-13T16:15:00+08:00' },
    { id: 'm-9', teamId: 'team-2', account: 'sun.shiyi', nickname: '孙十一', email: 'sun.shiyi@example.com', role: 'member', joinedAt: '2026-10-14T10:36:00+08:00' },
    { id: 'm-10', teamId: 'team-2', account: 'qian.shier', nickname: '钱十二', email: 'qian.shier@example.com', role: 'member', joinedAt: '2026-10-16T13:08:00+08:00' },
    { id: 'm-11', teamId: 'team-2', account: 'feng.shisan', nickname: '冯十三', email: 'feng.shisan@example.com', role: 'member', joinedAt: '2026-10-17T17:50:00+08:00' },
    { id: 'm-12', teamId: 'team-2', account: 'chu.shisi', nickname: '褚十四', email: 'chu.shisi@example.com', role: 'member', joinedAt: '2026-10-19T08:25:00+08:00' },
    { id: 'm-16', teamId: 'team-2', account: 'demo', nickname: 'demo', email: 'demo@example.com', role: 'member', joinedAt: '2026-10-06T14:05:00+08:00' },
  ],

  teamProjects: [
    // ---- team-2 搜索与推荐组 ----
    { id: 'p-1', teamId: 'team-2', name: '智能搜索 v3', description: 'BM25 + 向量混合检索改造，提升首点命中率与召回率。', ownerAccount: 'zhang.san', memberCount: 6, createdAt: '2026-10-08T10:00:00+08:00', sortOrder: 1 },
    { id: 'p-2', teamId: 'team-2', name: '推荐 Feed 重构', description: '多路召回 + 粗排 + 精排三段式链路升级。', ownerAccount: 'li.si', memberCount: 5, createdAt: '2026-10-10T16:30:00+08:00', sortOrder: 2 },
    { id: 'p-3', teamId: 'team-2', name: '语义召回服务', description: '基于 Embedding 的语义召回通道与冷启动内容优化。', ownerAccount: 'wang.wu', memberCount: 4, createdAt: '2026-10-12T11:20:00+08:00', sortOrder: 3 },
    { id: 'p-4', teamId: 'team-2', name: '评测平台', description: '检索与排序效果的离线评测、回归与 A/B 实验支持。', ownerAccount: 'zhao.liu', memberCount: 3, createdAt: '2026-10-15T09:00:00+08:00', sortOrder: 4 },
    { id: 'p-5', teamId: 'team-2', name: '数据标注平台', description: '标注任务分发、质检流程与标注数据回流管道。', ownerAccount: 'chen.qi', memberCount: 7, createdAt: '2026-10-18T14:45:00+08:00', sortOrder: 5 },
    { id: 'p-6', teamId: 'team-2', name: 'Query 理解', description: '查询改写、意图识别与实体链接。', ownerAccount: 'demo', memberCount: 3, createdAt: '2026-10-21T19:10:00+08:00', sortOrder: 6 },
  ],

  // 预置项目成员（演示账号 demo 为 p-6 负责人；访问其他项目时自动以成员身份加入）
  projectMembers: [
    // ---- p-1 智能搜索 v3（负责人 zhang.san）----
    { id: 'pm-1', projectId: 'p-1', account: 'zhang.san', nickname: '张三', email: 'zhang.san@example.com', role: 'owner', joinedAt: '2026-10-08T10:00:00+08:00' },
    { id: 'pm-2', projectId: 'p-1', account: 'li.si', nickname: '李四', email: 'li.si@example.com', role: 'member', joinedAt: '2026-10-08T15:20:00+08:00' },
    { id: 'pm-3', projectId: 'p-1', account: 'wang.wu', nickname: '王五', email: 'wang.wu@example.com', role: 'member', joinedAt: '2026-10-09T09:40:00+08:00' },
    { id: 'pm-4', projectId: 'p-1', account: 'zhao.liu', nickname: '赵六', email: 'zhao.liu@example.com', role: 'member', joinedAt: '2026-10-10T11:05:00+08:00' },
    { id: 'pm-5', projectId: 'p-1', account: 'chen.qi', nickname: '陈七', email: 'chen.qi@example.com', role: 'member', joinedAt: '2026-10-11T14:30:00+08:00' },
    // ---- p-2 推荐 Feed 重构（负责人 li.si）----
    { id: 'pm-6', projectId: 'p-2', account: 'li.si', nickname: '李四', email: 'li.si@example.com', role: 'owner', joinedAt: '2026-10-10T16:30:00+08:00' },
    { id: 'pm-7', projectId: 'p-2', account: 'wang.wu', nickname: '王五', email: 'wang.wu@example.com', role: 'member', joinedAt: '2026-10-11T10:12:00+08:00' },
    { id: 'pm-8', projectId: 'p-2', account: 'chen.qi', nickname: '陈七', email: 'chen.qi@example.com', role: 'member', joinedAt: '2026-10-12T16:45:00+08:00' },
    // ---- p-3 语义召回服务（负责人 wang.wu）----
    { id: 'pm-9', projectId: 'p-3', account: 'wang.wu', nickname: '王五', email: 'wang.wu@example.com', role: 'owner', joinedAt: '2026-10-12T11:20:00+08:00' },
    { id: 'pm-10', projectId: 'p-3', account: 'zhang.san', nickname: '张三', email: 'zhang.san@example.com', role: 'member', joinedAt: '2026-10-13T09:00:00+08:00' },
    // ---- p-4 评测平台（负责人 zhao.liu）----
    { id: 'pm-11', projectId: 'p-4', account: 'zhao.liu', nickname: '赵六', email: 'zhao.liu@example.com', role: 'owner', joinedAt: '2026-10-15T09:00:00+08:00' },
    { id: 'pm-12', projectId: 'p-4', account: 'li.si', nickname: '李四', email: 'li.si@example.com', role: 'member', joinedAt: '2026-10-15T13:30:00+08:00' },
    { id: 'pm-13', projectId: 'p-4', account: 'zhang.san', nickname: '张三', email: 'zhang.san@example.com', role: 'member', joinedAt: '2026-10-16T10:18:00+08:00' },
    // ---- p-5 数据标注平台（负责人 chen.qi）----
    { id: 'pm-14', projectId: 'p-5', account: 'chen.qi', nickname: '陈七', email: 'chen.qi@example.com', role: 'owner', joinedAt: '2026-10-18T14:45:00+08:00' },
    { id: 'pm-15', projectId: 'p-5', account: 'wang.wu', nickname: '王五', email: 'wang.wu@example.com', role: 'member', joinedAt: '2026-10-18T17:02:00+08:00' },
    { id: 'pm-16', projectId: 'p-5', account: 'zhou.ba', nickname: '周八', email: 'zhou.ba@example.com', role: 'member', joinedAt: '2026-10-19T09:26:00+08:00' },
    { id: 'pm-17', projectId: 'p-5', account: 'wu.jiu', nickname: '吴九', email: 'wu.jiu@example.com', role: 'member', joinedAt: '2026-10-20T15:40:00+08:00' },
    // ---- p-6 Query 理解（负责人 demo）----
    { id: 'pm-18', projectId: 'p-6', account: 'demo', nickname: 'demo', email: 'demo@example.com', role: 'owner', joinedAt: '2026-10-21T19:10:00+08:00' },
    { id: 'pm-19', projectId: 'p-6', account: 'zhang.san', nickname: '张三', email: 'zhang.san@example.com', role: 'member', joinedAt: '2026-10-21T20:05:00+08:00' },
    { id: 'pm-20', projectId: 'p-6', account: 'li.si', nickname: '李四', email: 'li.si@example.com', role: 'member', joinedAt: '2026-10-22T10:30:00+08:00' },
  ],

  knowledgeBases: [
    {
      id: 'kb-1',
      name: '产品需求文档库',
      description: '搜索与推荐团队的产品需求、评审记录与功能规格说明。',
      projectId: 'p-1',
      fileCount: 2,
      chunkCount: 8,
      createdAt: '2026-10-09T10:00:00+08:00',
      updatedAt: '2026-10-18T09:24:00+08:00',
      sortOrder: 1,
    },
    {
      id: 'kb-2',
      name: 'API 接口文档',
      description: 'LlamaIndex 服务端 OpenAPI 规范、调用示例与错误码字典。',
      projectId: 'p-1',
      fileCount: 2,
      chunkCount: 7,
      createdAt: '2026-10-11T14:00:00+08:00',
      updatedAt: '2026-10-17T16:40:00+08:00',
      sortOrder: 2,
    },
    {
      id: 'kb-3',
      name: '技术方案与评审',
      description: '架构设计文档、技术评审结论与 ADR（架构决策记录）。',
      projectId: 'p-2',
      fileCount: 1,
      chunkCount: 3,
      createdAt: '2026-10-12T09:00:00+08:00',
      updatedAt: '2026-10-15T11:05:00+08:00',
      sortOrder: 1,
    },
    {
      id: 'kb-4',
      name: '客户支持 FAQ',
      description: '客服常见问题与标准答复话术，等待上传首批文件。',
      projectId: 'p-3',
      fileCount: 0,
      chunkCount: 0,
      createdAt: '2026-10-13T18:30:00+08:00',
      updatedAt: '2026-10-12T18:30:00+08:00',
      sortOrder: 1,
    },
  ],

  files: [
    {
      id: 'f-1',
      kbId: 'kb-1',
      name: 'PRD-智能搜索-v2.3.pdf',
      size: 2_411_520,
      chunkCount: 5,
      status: 'indexed',
      strategyId: 's-1',
      updatedAt: '2026-10-18T09:24:00+08:00',
    },
    {
      id: 'f-2',
      kbId: 'kb-1',
      name: 'PRD-推荐Feed改版.docx',
      size: 1_024_000,
      chunkCount: 3,
      status: 'indexed',
      strategyId: 's-1',
      updatedAt: '2026-10-16T14:02:00+08:00',
    },
    {
      id: 'f-3',
      kbId: 'kb-2',
      name: 'openapi-llamaindex.yaml',
      size: 86_400,
      chunkCount: 4,
      status: 'indexed',
      strategyId: 's-3',
      updatedAt: '2026-10-17T16:40:00+08:00',
    },
    {
      id: 'f-4',
      kbId: 'kb-2',
      name: '错误码字典.md',
      size: 21_504,
      chunkCount: 3,
      status: 'indexed',
      strategyId: 's-3',
      updatedAt: '2026-10-14T10:12:00+08:00',
    },
    {
      id: 'f-5',
      kbId: 'kb-3',
      name: 'ADR-001-向量库选型.md',
      size: 34_816,
      chunkCount: 3,
      status: 'indexed',
      strategyId: 's-4',
      updatedAt: '2026-10-15T11:05:00+08:00',
    },
  ],

  // 策略按知识库归属；documentCount 由 files 中的 strategyId 实时统计
  parseStrategies: [
    {
      id: 's-1',
      kbId: 'kb-1',
      name: '默认文档策略',
      embedModel: 'bge-m3',
      stages: {
        parser: ['Docling'],
        pre_extract: [],
        split: [{ id: 'semantic', params: { breakpoint_percentile_threshold: 90 } }],
        post_extract: [
          { id: 'title', llm: 'qwen-max', params: {} },
          { id: 'summary', llm: 'qwen-max', params: {} },
        ],
      },
      graph: true,
      createdAt: '2026-10-09T10:00:00+08:00',
      updatedAt: '2026-10-18T09:24:00+08:00',
    },
    {
      id: 's-2',
      kbId: 'kb-1',
      name: '扫描件 OCR 策略',
      embedModel: 'bge-large-zh',
      stages: {
        parser: ['MonkeyOCRv2'],
        pre_extract: [],
        split: [{ id: 'sentence_window', params: {} }],
        post_extract: [{ id: 'entity', llm: 'qwen-max', params: {} }],
      },
      graph: true,
      createdAt: '2026-10-15T14:20:00+08:00',
      updatedAt: '2026-10-20T11:08:00+08:00',
    },
    {
      id: 's-3',
      kbId: 'kb-2',
      name: '接口文档策略',
      embedModel: 'bge-m3',
      stages: {
        parser: ['Docling'],
        pre_extract: [],
        split: [{ id: 'markdown', params: {} }],
        post_extract: [{ id: 'question', llm: 'qwen-max', params: {} }],
      },
      graph: false,
      createdAt: '2026-10-11T14:00:00+08:00',
      updatedAt: '2026-10-17T16:40:00+08:00',
    },
    {
      id: 's-4',
      kbId: 'kb-3',
      name: '技术方案策略',
      embedModel: 'bge-m3',
      stages: {
        parser: ['Docling'],
        pre_extract: [],
        split: [{ id: 'hierarchical', params: { chunk_sizes: '2048, 512, 128' } }],
        post_extract: [{ id: 'keyword', llm: 'qwen-max', params: {} }],
      },
      graph: true,
      createdAt: '2026-10-12T09:00:00+08:00',
      updatedAt: '2026-10-15T11:05:00+08:00',
    },
    {
      id: 's-5',
      kbId: 'kb-4',
      name: '客服 FAQ 策略',
      embedModel: 'bge-large-zh',
      stages: {
        parser: ['Docling'],
        pre_extract: [],
        split: [{ id: 'sentence', params: { chunk_size: 300, chunk_overlap: 60 } }],
        post_extract: [{ id: 'question', llm: 'qwen-max', params: {} }],
      },
      graph: false,
      createdAt: '2026-10-13T18:30:00+08:00',
      updatedAt: '2026-10-13T18:30:00+08:00',
    },
  ],

  chunks: [
    // ---- f-1 PRD-智能搜索 ----
    {
      id: 'c-1',
      fileId: 'f-1',
      index: 1,
      content:
        '1.1 背景\n当前站内搜索的召回率仅为 62%，用户平均需要 3.2 次改写关键词才能命中目标内容。随着知识库文档量突破 50 万篇，基于关键词倒排索引的传统方案已难以覆盖语义级检索需求。',
      tokens: 128,
      metadata: { source: 'PRD-智能搜索-v2.3.pdf', page: '2', section: '背景与问题', version: 'v2.3' },
      updatedAt: '2026-10-18T09:24:00+08:00',
    },
    {
      id: 'c-2',
      fileId: 'f-1',
      index: 2,
      content:
        '1.2 目标\n本期改版引入向量混合检索（BM25 + Embedding），目标：① 首次命中率提升至 85% 以上；② P95 检索延迟控制在 300ms 以内；③ 支持按知识库维度进行权限隔离与过滤。',
      tokens: 96,
      metadata: { source: 'PRD-智能搜索-v2.3.pdf', page: '3', section: '产品目标', version: 'v2.3' },
      updatedAt: '2026-10-18T09:24:00+08:00',
    },
    {
      id: 'c-3',
      fileId: 'f-1',
      index: 3,
      content:
        '2.1 分块策略\n文档入库时按 512 token 滑窗切分，重叠 64 token；对 Markdown 文档优先按标题层级切分，保证单个分块语义完整。表格类内容整表保留，不跨块拆分。',
      tokens: 88,
      metadata: { source: 'PRD-智能搜索-v2.3.pdf', page: '5', section: '功能需求', type: '策略' },
      updatedAt: '2026-10-18T09:24:00+08:00',
    },
    {
      id: 'c-4',
      fileId: 'f-1',
      index: 4,
      content:
        '3.2 非功能需求\n可用性：检索服务可用性 ≥ 99.95%；安全：所有查询需经过租户级鉴权，跨租户文档不可见；合规：用户查询日志保留 180 天后自动脱敏归档。',
      tokens: 76,
      metadata: { source: 'PRD-智能搜索-v2.3.pdf', page: '9', section: '非功能需求', version: 'v2.3' },
      updatedAt: '2026-10-18T09:24:00+08:00',
    },
    {
      id: 'c-5',
      fileId: 'f-1',
      index: 5,
      content:
        '4.1 里程碑\nT1（10 月底）：分块与索引管线灰度；T2（11 月中）：混合检索全量；T3（12 月初）：RAG 问答入口上线，支持引用溯源展示。',
      tokens: 64,
      metadata: { source: 'PRD-智能搜索-v2.3.pdf', page: '12', section: '里程碑', owner: '产品组' },
      updatedAt: '2026-10-18T09:24:00+08:00',
    },
    // ---- f-2 推荐Feed改版 ----
    {
      id: 'c-6',
      fileId: 'f-2',
      index: 1,
      content:
        '一、改版概述\n推荐 Feed 由纯协同过滤升级为「多路召回 + 粗排 + 精排」三段式架构，召回侧新增基于知识库 Embedding 的语义召回通道，解决冷启动内容曝光不足的问题。',
      tokens: 84,
      metadata: { source: 'PRD-推荐Feed改版.docx', section: '改版概述', version: 'v1.0' },
      updatedAt: '2026-10-16T14:02:00+08:00',
    },
    {
      id: 'c-7',
      fileId: 'f-2',
      index: 2,
      content:
        '二、排序策略\n精排模型由 GBDT 升级为双塔 DNN，特征新增：文档新鲜度、知识库归属权重、用户近期负反馈。目标人均有效阅读时长 +12%，负反馈率 −8%。',
      tokens: 72,
      metadata: { source: 'PRD-推荐Feed改版.docx', section: '排序策略', owner: '算法组' },
      updatedAt: '2026-10-16T14:02:00+08:00',
    },
    {
      id: 'c-8',
      fileId: 'f-2',
      index: 3,
      content:
        '三、灰度计划\n按设备号尾号 5% → 20% → 50% → 100% 逐级放量，每级观察 48 小时，核心指标回退超阈值自动熔断并回滚。',
      tokens: 56,
      metadata: { source: 'PRD-推荐Feed改版.docx', section: '灰度计划', type: '流程' },
      updatedAt: '2026-10-16T14:02:00+08:00',
    },
    // ---- f-3 openapi ----
    {
      id: 'c-9',
      fileId: 'f-3',
      index: 1,
      content:
        'POST /v1/knowledge-bases\n创建知识库。请求体：{ "name": string (必填, ≤64 字符), "description": string (可选, ≤256 字符) }。返回 201 与完整知识库对象；重名时返回 409 KnowledgeBaseExists。',
      tokens: 92,
      metadata: { source: 'openapi-llamaindex.yaml', path: '/v1/knowledge-bases', method: 'POST' },
      updatedAt: '2026-10-17T16:40:00+08:00',
    },
    {
      id: 'c-10',
      fileId: 'f-3',
      index: 2,
      content:
        'POST /v1/knowledge-bases/{kbId}/files\n上传文件并触发解析。multipart/form-data，字段名 files，单文件 ≤ 50MB，单次 ≤ 20 个。返回文件对象列表，status 初始为 processing。',
      tokens: 90,
      metadata: { source: 'openapi-llamaindex.yaml', path: '/v1/knowledge-bases/{kbId}/files', method: 'POST' },
      updatedAt: '2026-10-17T16:40:00+08:00',
    },
    {
      id: 'c-11',
      fileId: 'f-3',
      index: 3,
      content:
        'GET /v1/files/{fileId}/chunks?cursor=&limit=50\n分页获取文件分块。cursor 为上一页最后一条的 id，limit 默认 50、上限 200。响应包含 items[] 与 nextCursor。',
      tokens: 70,
      metadata: { source: 'openapi-llamaindex.yaml', path: '/v1/files/{fileId}/chunks', method: 'GET' },
      updatedAt: '2026-10-17T16:40:00+08:00',
    },
    {
      id: 'c-12',
      fileId: 'f-3',
      index: 4,
      content:
        'PATCH /v1/chunks/{chunkId}\n更新分块。支持增量更新 content 与 metadata：传入字段即覆盖，未传字段保持原值。metadata 为整键覆盖语义（键级 replace，非深层 merge）。',
      tokens: 76,
      metadata: { source: 'openapi-llamaindex.yaml', path: '/v1/chunks/{chunkId}', method: 'PATCH' },
      updatedAt: '2026-10-17T16:40:00+08:00',
    },
    // ---- f-4 错误码 ----
    {
      id: 'c-13',
      fileId: 'f-4',
      index: 1,
      content:
        '401 Unauthorized\n凭证缺失或过期。响应体含 error.code = "AuthExpired"；客户端应静默刷新凭证并重放一次请求，重放仍失败则引导重新登录。',
      tokens: 58,
      metadata: { source: '错误码字典.md', code: '401', severity: '中' },
      updatedAt: '2026-10-14T10:12:00+08:00',
    },
    {
      id: 'c-14',
      fileId: 'f-4',
      index: 2,
      content:
        '413 PayloadTooLarge\n上传文件超过 50MB 限制。建议客户端前置校验文件大小，并对大 PDF 提示使用「分卷上传」通道。',
      tokens: 44,
      metadata: { source: '错误码字典.md', code: '413', severity: '低' },
      updatedAt: '2026-10-14T10:12:00+08:00',
    },
    {
      id: 'c-15',
      fileId: 'f-4',
      index: 3,
      content:
        '429 RateLimited\n触发限流。响应头 Retry-After 指示等待秒数；SDK 内置指数退避重试（最多 3 次），服务端按租户维度 1000 QPS 限流。',
      tokens: 52,
      metadata: { source: '错误码字典.md', code: '429', severity: '中' },
      updatedAt: '2026-10-14T10:12:00+08:00',
    },
    // ---- f-5 ADR ----
    {
      id: 'c-16',
      fileId: 'f-5',
      index: 1,
      content:
        '背景\n候选方案：pgvector（复用现有 PostgreSQL）与 Milvus（专用向量数据库）。评估维度：千万级向量下的检索延迟、运维成本、与现有权限体系集成难度。',
      tokens: 66,
      metadata: { source: 'ADR-001-向量库选型.md', section: '背景', status: 'accepted' },
      updatedAt: '2026-10-15T11:05:00+08:00',
    },
    {
      id: 'c-17',
      fileId: 'f-5',
      index: 2,
      content:
        '决策\n选择 pgvector：① 数据规模预期 2000 万以内，HNSW 索引 P95 < 80ms，满足需求；② 免去新增一套存储的运维负担；③ 权限过滤可直接用 SQL WHERE 表达，避免应用层二次过滤。',
      tokens: 78,
      metadata: { source: 'ADR-001-向量库选型.md', section: '决策', status: 'accepted' },
      updatedAt: '2026-10-15T11:05:00+08:00',
    },
    {
      id: 'c-18',
      fileId: 'f-5',
      index: 3,
      content:
        '影响与回退\n需为 pgvector 预留 3 倍于原始文档的存储空间；若规模超预期，预留 Milvus 迁移路径（Embedding 生成与业务层解耦，切换仅影响存储适配层）。',
      tokens: 64,
      metadata: { source: 'ADR-001-向量库选型.md', section: '影响', status: 'accepted' },
      updatedAt: '2026-10-15T11:05:00+08:00',
    },
  ],
}
