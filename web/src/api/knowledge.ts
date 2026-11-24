/**
 * 知识库模块 API 层（知识库详情已接后端，其余为 mock 暂代实现）
 * ------------------------------------------------------------------
 * ⚠️ 其余函数内部为「注释中的真实调用约定 + 内存 mock 实现」。
 * TODO(backend): 后端开发完成后，将各函数体内的 mock 实现替换为
 *   注释中标注的真实 HTTP 调用，并删除 src/mock 目录。
 *
 * 已接后端：
 *   GET    /api/knowledge-bases/{kbId}                知识库详情（含 projectId/teamId）
 *   GET    /api/knowledge-bases/{kbId}/files          文件列表
 *   POST   /api/knowledge-bases/{kbId}/files/upload   上传文件 (multipart, field: files, 可选 strategyId)
 *   GET    /api/files/{fileId}/content                下载文件原内容 (blob)
 *   DELETE /api/files/{fileId}/delete                 删除文件（清理解析任务/MinIO/向量/分块/记录）
 *   GET    /api/knowledge-bases/{kbId}/parse-strategies                   文件处理策略列表
 *   POST   /api/knowledge-bases/{kbId}/parse-strategies/create            新建文件处理策略
 *   GET    /api/knowledge-bases/{kbId}/parse-strategies/{strategyId}      文件处理策略详情
 *   PATCH  /api/knowledge-bases/{kbId}/parse-strategies/{strategyId}/update  修改文件处理策略
 *   DELETE /api/knowledge-bases/{kbId}/parse-strategies/{strategyId}/delete  删除文件处理策略
 *   GET    /api/knowledge-bases/{kbId}/graph-schema      知识库图谱schema（未创建为 null）
 *   PUT    /api/knowledge-bases/{kbId}/graph-schema      创建/修改知识库图谱schema（整体覆盖）
 *   GET    /api/files/{fileId}/chunks                  文件分块预览（分页，全量拉齐）
 *
 * 接口约定总览（其余仍为 mock）：
 *   GET    /api/knowledge-bases                       知识库列表
 *   POST   /api/knowledge-bases                       新建知识库
 *   GET    /api/knowledge-bases/{kbId}/files          文件列表
 *   POST   /api/knowledge-bases/{kbId}/files/upload   上传文件 (multipart)
 *   GET    /api/files/{fileId}/content                下载文件原内容 (blob)
 */

import type {
  Chunk,
  FileParseStrategy,
  FileParseStrategyPatch,
  GraphSchema,
  KnowledgeBase,
  KnowledgeFile,
} from '@/types/knowledge'
import { BASE, request } from './http'
import { db, genId } from '@/mock/store'

/** 模拟网络延迟 */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** ---------------- 知识库 ---------------- */

/** GET /api/knowledge-bases/{kbId}（附带 projectId/teamId，项目成员可查） */
export async function getKnowledgeBase(kbId: string): Promise<KnowledgeBase> {
  return request<KnowledgeBase>(`/knowledge-bases/${kbId}`)
}

/** GET /api/knowledge-bases */
export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  // TODO(backend): return http.get('/api/knowledge-bases')
  await delay(300)
  return structuredClone(db.knowledgeBases)
}

/** POST /api/knowledge-bases  body: { name, description } */
export async function createKnowledgeBase(name: string, description: string): Promise<KnowledgeBase> {
  // TODO(backend): return http.post('/api/knowledge-bases', { name, description })
  await delay(500)
  const now = new Date().toISOString()
  const kb: KnowledgeBase = {
    id: genId('kb'),
    name: name.trim(),
    description: description.trim(),
    fileCount: 0,
    chunkCount: 0,
    createdAt: now,
    updatedAt: now,
  }
  db.knowledgeBases.unshift(kb)
  return structuredClone(kb)
}

/** ---------------- 文件处理策略 ---------------- */

/** patch → 后端请求体（snake_case，仅提交的字段；stages 编排序列优先，单值字段由后端派生） */
function toStrategyBody(patch: Partial<FileParseStrategyPatch>): Record<string, unknown> {
  return {
    ...(patch.name !== undefined ? { name: patch.name } : {}),
    ...(patch.embedModel !== undefined ? { embed_model: patch.embedModel } : {}),
    ...(patch.graph !== undefined ? { graph: patch.graph } : {}),
    ...(patch.stages !== undefined ? { stages: patch.stages } : {}),
  }
}

/** ---------------- 图谱schema ---------------- */

/** GET /api/knowledge-bases/{kbId}/graph-schema（未创建时返回 null） */
export async function getGraphSchema(kbId: string): Promise<GraphSchema | null> {
  return request<GraphSchema | null>(`/knowledge-bases/${kbId}/graph-schema`)
}

/**
 * PUT /api/knowledge-bases/{kbId}/graph-schema
 * 创建/修改知识库图谱schema（整体覆盖保存）
 */
export async function saveGraphSchema(
  kbId: string,
  schema: Pick<GraphSchema, 'entities' | 'relations'>,
): Promise<GraphSchema> {
  return request<GraphSchema>(`/knowledge-bases/${kbId}/graph-schema`, {
    method: 'PUT',
    body: { entities: schema.entities, relations: schema.relations },
  })
}

/** GET /api/knowledge-bases/{kbId}/parse-strategies */
export async function listParseStrategies(kbId: string): Promise<FileParseStrategy[]> {
  return request<FileParseStrategy[]>(`/knowledge-bases/${kbId}/parse-strategies`)
}

/** POST /api/knowledge-bases/{kbId}/parse-strategies/create  body: FileParseStrategyPatch */
export async function createParseStrategy(
  kbId: string,
  patch: FileParseStrategyPatch,
): Promise<FileParseStrategy> {
  return request<FileParseStrategy>(`/knowledge-bases/${kbId}/parse-strategies/create`, {
    method: 'POST',
    body: toStrategyBody(patch),
  })
}

/** GET /api/knowledge-bases/{kbId}/parse-strategies/{strategyId} */
export async function getParseStrategy(
  kbId: string,
  strategyId: string,
): Promise<FileParseStrategy> {
  return request<FileParseStrategy>(`/knowledge-bases/${kbId}/parse-strategies/${strategyId}`)
}

/**
 * PATCH /api/knowledge-bases/{kbId}/parse-strategies/{strategyId}/update
 * 已被文档引用的策略不允许修改，需先调整相关文档的处理策略。
 */
export async function updateParseStrategy(
  kbId: string,
  strategyId: string,
  patch: FileParseStrategyPatch,
): Promise<FileParseStrategy> {
  return request<FileParseStrategy>(`/knowledge-bases/${kbId}/parse-strategies/${strategyId}/update`, {
    method: 'PATCH',
    body: toStrategyBody(patch),
  })
}

/**
 * DELETE /api/knowledge-bases/{kbId}/parse-strategies/{strategyId}/delete
 * 已被文档引用的策略不允许删除，需先调整相关文档的处理策略。
 */
export async function deleteParseStrategy(kbId: string, strategyId: string): Promise<void> {
  await request(`/knowledge-bases/${kbId}/parse-strategies/${strategyId}/delete`, { method: 'DELETE' })
}

/** ---------------- 文件 ---------------- */

/** GET /api/knowledge-bases/{kbId}/files */
export async function listFiles(kbId: string): Promise<KnowledgeFile[]> {
  return request<KnowledgeFile[]>(`/knowledge-bases/${kbId}/files`)
}

/**
 * DELETE /api/files/{fileId}/delete
 * 删除文件：后端清理解析任务(Redis)、MinIO对象、向量分块与文件记录，不可恢复。
 */
export async function deleteFile(fileId: string): Promise<void> {
  await request(`/files/${fileId}/delete`, { method: 'DELETE' })
}

/**
 * DELETE /api/knowledge-bases/{kbId}/delete
 * 删除知识库：后端级联清理文件（解析任务/MinIO/向量/分块）、处理策略与知识库记录，不可恢复。
 */
export async function deleteKnowledgeBase(kbId: string): Promise<void> {
  await request(`/knowledge-bases/${kbId}/delete`, { method: 'DELETE' })
}

/**
 * POST /api/knowledge-bases/{kbId}/files/upload  (multipart/form-data, field: files)
 * 返回新创建的文件记录（status 初始为 processing，索引完成后由后端置为 indexed）
 */
export async function uploadFiles(
  kbId: string,
  files: File[],
  strategyId?: string,
): Promise<KnowledgeFile[]> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  if (strategyId) form.append('strategy_id', strategyId)
  return request<KnowledgeFile[]>(`/knowledge-bases/${kbId}/files/upload`, {
    method: 'POST',
    formData: form,
  })
}

/**
 * GET /api/files/{fileId}/content  二进制流响应（非统一信封），由调用方触发浏览器保存
 * 不走 request()：request 会按 JSON 信封解析，无法承载 blob
 */
export async function downloadFile(fileId: string): Promise<Blob> {
  const { getAccessToken } = await import('@/stores/auth')
  const headers: Record<string, string> = {}
  const token = getAccessToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}/files/${fileId}/content`, { headers })
  if (!res.ok) throw new Error(`下载失败（${res.status}）`)
  return res.blob()
}

/** ---------------- 分块 ---------------- */

/** 后端分块响应结构（GET /api/files/{fileId}/chunks） */
interface ChunkPage {
  total: number
  chunks: { nodeId: string; text: string; metadata: Record<string, unknown>; createdAt: string | null }[]
}

/**
 * GET /api/files/{fileId}/chunks  文件分块预览（docstore切分节点，仅解析成功的文件有数据）
 * 后端分页返回（单页上限100）；预览页为全量展示+客户端搜索，这里按 total 并行拉齐所有页
 */
export async function listChunks(fileId: string): Promise<Chunk[]> {
  const PAGE_SIZE = 100
  const first: ChunkPage = await request<ChunkPage>(
    `/files/${fileId}/chunks?page=1&page_size=${PAGE_SIZE}`,
  )
  const pages = Math.ceil(first.total / PAGE_SIZE)
  if (pages <= 1) return first.chunks.map(toChunk(0))
  const rest = await Promise.all(
    Array.from({ length: pages - 1 }, (_, i) =>
      request<ChunkPage>(`/files/${fileId}/chunks?page=${i + 2}&page_size=${PAGE_SIZE}`),
    ),
  )
  return [first, ...rest].flatMap((p, pageNo) => p.chunks.map(toChunk(pageNo * PAGE_SIZE)))
}

/** 后端分块 → 前端Chunk：tokens为粗略估算（与历史mock口径一致），metadata统一转字符串 */
function toChunk(offset: number) {
  return (chunk: ChunkPage['chunks'][number], i: number): Chunk => ({
    id: chunk.nodeId,
    fileId: '',
    index: offset + i + 1,
    content: chunk.text,
    tokens: Math.max(1, Math.round(chunk.text.length / 1.6)),
    metadata: Object.fromEntries(
      Object.entries(chunk.metadata).map(([k, v]) => [k, String(v)]),
    ),
    updatedAt: chunk.createdAt ?? '',
  })
}
