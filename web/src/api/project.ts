/**
 * 项目模块 API 层（项目详情/项目成员列表/我的项目成员信息/知识库列表与创建已接后端，其余仍为 mock 暂代实现）
 * ------------------------------------------------------------------
 * ⚠️ 与 src/api/team.ts 相同模式：函数体内为「注释中的真实调用约定 +
 *    内存 mock 实现」。
 * TODO(backend): 后端开发完成后，将各函数体内的 mock 实现替换为
 *   注释中标注的真实 HTTP 调用，并删除 src/mock 目录。
 *
 * 已接后端（鉴权经统一拦截器，request 自动携带AT并处理40102静默刷新）：
 *   GET    /api/projects/{projectId}                        项目详情（含负责人昵称）
 *   GET    /api/projects/{projectId}/members                项目成员分页列表 ?query=&page=&page_size=
 *   GET    /api/projects/{projectId}/members/me             我的项目成员信息（首次进入自动加入）
 *   GET    /api/projects/{projectId}/knowledge-bases        项目知识库列表
 *   POST   /api/projects/{projectId}/knowledge-bases/create 新建项目知识库 body: { name, description? }
 *
 * 接口约定总览（其余仍为 mock）：
 *   DELETE /api/projects/{projectId}                        解散项目（删除项目全部数据）
 *   PATCH  /api/projects/{projectId}/members/me             修改我的项目内昵称 body: { nickname }
 *   DELETE /api/projects/{projectId}/members/me             退出项目
 *   POST   /api/projects/{projectId}/members/add           添加项目成员 body: { account }
 *   DELETE /api/projects/{projectId}/members/{memberId}     移出项目成员
 *   POST   /api/projects/{projectId}/transfer               移交项目负责人 body: { memberId }
 *   PATCH  /api/projects/{projectId}/knowledge-bases/order  项目知识库自定义排序 body: { kbIds }
 */

import { request } from './http'
import type { KnowledgeBase } from '@/types/knowledge'
import type {
  ProjectMember,
  ProjectMemberPage,
  ProjectRole,
  ProjectView,
  TeamProject,
} from '@/types/team'
import { db, genId } from '@/mock/store'
import { currentUser } from '@/stores/auth'

/** 模拟网络延迟 */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function currentAccount(): string {
  const account = currentUser.value?.account
  if (!account) throw new Error('未登录')
  return account
}

function requireProject(projectId: string): TeamProject {
  const project = db.teamProjects.find((p) => p.id === projectId)
  if (!project) throw new Error('项目不存在')
  return project
}

/**
 * 确保当前登录用户在项目中存在成员记录（mock 语义：首次访问项目时自动加入）。
 * 项目已有负责人 → 以「项目成员」身份加入；否则成为「项目负责人」。
 */
function ensureProjectMembership(projectId: string): ProjectMember {
  const account = currentAccount()
  const existing = db.projectMembers.find(
    (m) => m.projectId === projectId && m.account === account,
  )
  if (existing) return existing
  const role: ProjectRole = db.projectMembers.some(
    (m) => m.projectId === projectId && m.role === 'owner',
  )
    ? 'member'
    : 'owner'
  const me: ProjectMember = {
    id: genId('pm'),
    projectId,
    account,
    nickname: account,
    email: `${account}@example.com`,
    role,
    joinedAt: new Date().toISOString(),
  }
  db.projectMembers.push(me)
  return me
}

/** ---------------- 项目 ---------------- */

/** GET /api/projects/{projectId}（附带负责人昵称） */
export async function getProject(projectId: string): Promise<ProjectView> {
  return request<ProjectView>(`/projects/${projectId}`)
}

/** DELETE /api/projects/{projectId}/delete（解散：级联删除项目、知识库、文件全部数据） */
export async function deleteProject(projectId: string): Promise<void> {
  await request(`/projects/${projectId}/delete`, { method: 'DELETE' })
}

/** ---------------- 项目成员 ---------------- */

/** GET /api/projects/{projectId}/members/me */
export async function getMyProjectMembership(projectId: string): Promise<ProjectMember> {
  return request<ProjectMember>(`/projects/${projectId}/members/me`)
}

/** PATCH /api/projects/{projectId}/members/me  body: { nickname } */
export async function updateMyProjectNickname(
  projectId: string,
  nickname: string,
): Promise<ProjectMember> {
  // TODO(backend): return http.patch(`/api/projects/${projectId}/members/me`, { nickname })
  await delay(400)
  const me = ensureProjectMembership(projectId)
  me.nickname = nickname.trim()
  return structuredClone(me)
}

/** DELETE /api/projects/{projectId}/members/me（退出项目，负责人不可退出） */
export async function leaveProject(projectId: string): Promise<void> {
  // TODO(backend): return http.delete(`/api/projects/${projectId}/members/me`)
  await delay(400)
  const me = ensureProjectMembership(projectId)
  if (me.role === 'owner') throw new Error('项目负责人请先移交或解散项目')
  db.projectMembers = db.projectMembers.filter((m) => m.id !== me.id)
}

/** GET /api/projects/{projectId}/members?query=&page=&page_size=（昵称/账号模糊搜索，负责人置顶） */
export async function listProjectMembers(
  projectId: string,
  opts: { query?: string; page?: number; pageSize?: number } = {},
): Promise<ProjectMemberPage> {
  const params = new URLSearchParams()
  if (opts.query?.trim()) params.set('query', opts.query.trim())
  if (opts.page) params.set('page', String(opts.page))
  if (opts.pageSize) params.set('page_size', String(opts.pageSize))
  const query = params.toString()
  return request<ProjectMemberPage>(`/projects/${projectId}/members${query ? `?${query}` : ''}`)
}

/** POST /api/projects/{projectId}/members/add  body: { account }（添加项目成员，账号来自团队成员搜索） */
export async function addProjectMember(
  projectId: string,
  account: string,
): Promise<ProjectMember> {
  return request<ProjectMember>(`/projects/${projectId}/members/add`, {
    method: 'POST',
    body: { account: account.trim() },
  })
}

/** DELETE /api/projects/{projectId}/members/{memberId}（移出项目成员，负责人不可被移出） */
export async function removeProjectMember(projectId: string, memberId: string): Promise<void> {
  // TODO(backend): return http.delete(`/api/projects/${projectId}/members/${memberId}`)
  await delay(400)
  const member = db.projectMembers.find((m) => m.id === memberId && m.projectId === projectId)
  if (!member) throw new Error('成员不存在')
  if (member.role === 'owner') throw new Error('无法移出项目负责人')
  db.projectMembers = db.projectMembers.filter((m) => m.id !== memberId)
}

/** POST /api/projects/{projectId}/transfer  body: { memberId }（移交负责人，自身变为项目成员） */
export async function transferProjectOwnership(
  projectId: string,
  memberId: string,
): Promise<void> {
  // TODO(backend): return http.post(`/api/projects/${projectId}/transfer`, { memberId })
  await delay(500)
  const me = ensureProjectMembership(projectId)
  const target = db.projectMembers.find((m) => m.id === memberId && m.projectId === projectId)
  if (!target) throw new Error('成员不存在')
  if (target.id === me.id) throw new Error('不能移交给自已')
  me.role = 'member'
  target.role = 'owner'
  // 同步项目表的负责人
  const project = requireProject(projectId)
  project.ownerAccount = target.account
}

/** ---------------- 项目知识库 ---------------- */

/** GET /api/projects/{projectId}/knowledge-bases（按自定义排序值返回） */
export async function listProjectKnowledgeBases(projectId: string): Promise<KnowledgeBase[]> {
  return request<KnowledgeBase[]>(`/projects/${projectId}/knowledge-bases`)
}

/** POST /api/projects/{projectId}/knowledge-bases/create  body: { name, description?, embed_model? } */
export async function createProjectKnowledgeBase(
  projectId: string,
  name: string,
  description = '',
  embedModel = 'bge-m3',
): Promise<KnowledgeBase> {
  return request<KnowledgeBase>(`/projects/${projectId}/knowledge-bases/create`, {
    method: 'POST',
    body: { name: name.trim(), description: description.trim(), embed_model: embedModel.trim() || 'bge-m3' },
  })
}

/** PATCH /api/projects/{projectId}/knowledge-bases/order  body: { kbIds }（按数组顺序写入自定义排序） */
export async function updateProjectKnowledgeBaseOrder(
  projectId: string,
  kbIds: string[],
): Promise<void> {
  // TODO(backend): return http.patch(`/api/projects/${projectId}/knowledge-bases/order`, { kbIds })
  await delay(200)
  kbIds.forEach((id, index) => {
    const kb = db.knowledgeBases.find((k) => k.id === id && k.projectId === projectId)
    if (kb) kb.sortOrder = index + 1
  })
}
