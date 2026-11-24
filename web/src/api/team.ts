/**
 * 团队模块 API 层（团队/项目创建与查询已接后端，成员管理仍为 mock 暂代实现）
 * ------------------------------------------------------------------
 * 已接后端（鉴权经统一拦截器，request 自动携带AT并处理40102静默刷新）：
 *   POST   /api/teams/list                             我参与的团队列表（含我的角色）
 *   POST   /api/teams/create                           新建团队 body: { name, description? }
 *   GET    /api/teams/{teamId}/members/me              我的成员信息
 *   GET    /api/teams/{teamId}/members                 成员分页列表 ?page=&page_size=
 *   GET    /api/teams/{teamId}/projects                项目列表（含负责人昵称）
 *   POST   /api/teams/{teamId}/projects/create         新建项目 body: { name, description?, owner_account? }
 *
 * 仍为 mock（TODO(backend)）：接口约定见下方各函数注释，联调后替换。
 *   PATCH  /api/teams/{teamId}                          更新团队信息 body: { name?, description? }
 *   DELETE /api/teams/{teamId}                          解散团队（删除团队全部数据）
 *   PATCH  /api/teams/{teamId}/members/me               修改我的团队内昵称 body: { nickname }
 *   DELETE /api/teams/{teamId}/members/me               退出团队
 *   POST   /api/teams/{teamId}/members/add             添加成员 body: { account }
 *   DELETE /api/teams/{teamId}/members/{memberId}       移出成员
 *   POST   /api/teams/{teamId}/transfer                 移交所有权 body: { memberId }
 *   PATCH  /api/teams/{teamId}/projects/order           项目自定义排序 body: { projectIds }
 */

import { currentUser } from '@/stores/auth'
import { request } from './http'
import type {
  MemberPage,
  ProjectView,
  Team,
  TeamMember,
  TeamRole,
  TeamWithRole,
} from '@/types/team'
import { db, genId } from '@/mock/store'
import type { SystemAccount } from '@/types/team'

/** 模拟网络延迟 */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function currentAccount(): string {
  const account = currentUser.value?.account
  if (!account) throw new Error('未登录')
  return account
}

function requireTeam(teamId: string): Team {
  const team = db.teams.find((t) => t.id === teamId)
  if (!team) throw new Error('团队不存在')
  return team
}

/** 按成员表解析成员展示名（昵称，缺失时回退账号） */
export function memberName(teamId: string, account: string): string {
  return (
    db.teamMembers.find((m) => m.teamId === teamId && m.account === account)?.nickname ?? account
  )
}

/**
 * 确保当前登录用户在团队中存在成员记录（mock 语义：种子团队首次访问时自动加入）。
 * 团队已有所有者 → 以「成员」身份加入；否则成为「所有者」。
 */
function ensureMembership(teamId: string): TeamMember {
  const account = currentAccount()
  const existing = db.teamMembers.find((m) => m.teamId === teamId && m.account === account)
  if (existing) return existing
  const role: TeamRole = db.teamMembers.some((m) => m.teamId === teamId && m.role === 'owner')
    ? 'member'
    : 'owner'
  const me: TeamMember = {
    id: genId('m'),
    teamId,
    account,
    nickname: account,
    email: `${account}@example.com`,
    role,
    joinedAt: new Date().toISOString(),
  }
  db.teamMembers.push(me)
  return me
}

/** ---------------- 团队 ---------------- */

/** POST /api/teams/list（仅返回当前账号已加入的团队；空列表即「当前没有团队」） */
export async function listTeams(): Promise<TeamWithRole[]> {
  return request<TeamWithRole[]>('/teams/list', { method: 'POST' })
}

/** POST /api/teams/create  body: { name, description? }（创建者成为团队所有者） */
export async function createTeam(name: string, description = ''): Promise<Team> {
  return request<Team>('/teams/create', {
    method: 'POST',
    body: { name: name.trim(), description: description.trim() },
  })
}

/** PATCH /api/teams/{teamId}  body: { name?, description? }（仅团队所有者可修改） */
export async function updateTeam(
  teamId: string,
  patch: { name?: string; description?: string },
): Promise<Team> {
  // TODO(backend): return http.patch(`/api/teams/${teamId}`, patch)
  await delay(400)
  const me = ensureMembership(teamId)
  if (me.role !== 'owner') throw new Error('仅团队所有者可修改团队信息')
  const team = requireTeam(teamId)
  if (patch.name !== undefined) team.name = patch.name.trim()
  if (patch.description !== undefined) team.description = patch.description.trim()
  return structuredClone(team)
}

/** DELETE /api/teams/{teamId}/delete（解散：级联删除团队、项目、知识库、文件全部数据） */
export async function deleteTeam(teamId: string): Promise<void> {
  await request(`/teams/${teamId}/delete`, { method: 'DELETE' })
}

/** ---------------- 成员 ---------------- */

/** GET /api/teams/{teamId}/members/me */
export async function getMyMembership(teamId: string): Promise<TeamMember> {
  return request<TeamMember>(`/teams/${teamId}/members/me`)
}

/** PATCH /api/teams/{teamId}/members/me  body: { nickname } */
export async function updateMyNickname(teamId: string, nickname: string): Promise<TeamMember> {
  // TODO(backend): return http.patch(`/api/teams/${teamId}/members/me`, { nickname })
  await delay(400)
  const me = ensureMembership(teamId)
  me.nickname = nickname.trim()
  return structuredClone(me)
}

/** DELETE /api/teams/{teamId}/members/me（退出团队，所有者不可退出） */
export async function leaveTeam(teamId: string): Promise<void> {
  // TODO(backend): return http.delete(`/api/teams/${teamId}/members/me`)
  await delay(400)
  const me = ensureMembership(teamId)
  if (me.role === 'owner') throw new Error('团队所有者请先移交或解散团队')
  db.teamMembers = db.teamMembers.filter((m) => m.id !== me.id)
}

/** GET /api/teams/{teamId}/members?query=&page=&page_size=（昵称/账号模糊搜索，所有者置顶） */
export async function listMembers(
  teamId: string,
  opts: { query?: string; page?: number; pageSize?: number } = {},
): Promise<MemberPage> {
  const params = new URLSearchParams()
  if (opts.query?.trim()) params.set('query', opts.query.trim())
  if (opts.page) params.set('page', String(opts.page))
  if (opts.pageSize) params.set('page_size', String(opts.pageSize))
  const query = params.toString()
  return request<MemberPage>(`/teams/${teamId}/members${query ? `?${query}` : ''}`)
}

/** GET /api/accounts/search?query=（搜索系统所有正常状态账号，添加成员选人用） */
export async function searchAccounts(query = ''): Promise<SystemAccount[]> {
  const params = new URLSearchParams()
  if (query.trim()) params.set('query', query.trim())
  const qs = params.toString()
  return request<SystemAccount[]>(`/accounts/search${qs ? `?${qs}` : ''}`)
}

/** POST /api/teams/{teamId}/members/add  body: { account }（添加团队成员，账号来自系统账号搜索） */
export async function addMember(teamId: string, account: string): Promise<TeamMember> {
  return request<TeamMember>(`/teams/${teamId}/members/add`, {
    method: 'POST',
    body: { account: account.trim() },
  })
}

/** DELETE /api/teams/{teamId}/members/{memberId}（移出成员，所有者不可被移出） */
export async function removeMember(teamId: string, memberId: string): Promise<void> {
  // TODO(backend): return http.delete(`/api/teams/${teamId}/members/${memberId}`)
  await delay(400)
  const member = db.teamMembers.find((m) => m.id === memberId && m.teamId === teamId)
  if (!member) throw new Error('成员不存在')
  if (member.role === 'owner') throw new Error('无法移出团队所有者')
  db.teamMembers = db.teamMembers.filter((m) => m.id !== memberId)
}

/** POST /api/teams/{teamId}/transfer  body: { memberId }（移交所有权，自身变为成员） */
export async function transferOwnership(teamId: string, memberId: string): Promise<void> {
  // TODO(backend): return http.post(`/api/teams/${teamId}/transfer`, { memberId })
  await delay(500)
  const me = ensureMembership(teamId)
  const target = db.teamMembers.find((m) => m.id === memberId && m.teamId === teamId)
  if (!target) throw new Error('成员不存在')
  if (target.id === me.id) throw new Error('不能移交给自已')
  me.role = 'member'
  target.role = 'owner'
}

/** ---------------- 项目 ---------------- */

/** GET /api/teams/{teamId}/projects（按自定义排序值返回，附带负责人昵称） */
export async function listProjects(teamId: string): Promise<ProjectView[]> {
  return request<ProjectView[]>(`/teams/${teamId}/projects`)
}

/** POST /api/teams/{teamId}/projects/create  body: { name, description?, owner_account? }
 *  owner_account 缺省时创建者为项目负责人；指定时创建者以项目成员身份加入 */
export async function createProject(
  teamId: string,
  name: string,
  description = '',
  ownerAccount?: string,
): Promise<ProjectView> {
  return request<ProjectView>(`/teams/${teamId}/projects/create`, {
    method: 'POST',
    body: {
      name: name.trim(),
      description: description.trim(),
      ...(ownerAccount ? { owner_account: ownerAccount } : {}),
    },
  })
}

/** PATCH /api/teams/{teamId}/projects/order  body: { projectIds }（按数组顺序写入自定义排序） */
export async function updateProjectOrder(teamId: string, projectIds: string[]): Promise<void> {
  // TODO(backend): return http.patch(`/api/teams/${teamId}/projects/order`, { projectIds })
  await delay(200)
  projectIds.forEach((id, index) => {
    const project = db.teamProjects.find((p) => p.id === id && p.teamId === teamId)
    if (project) project.sortOrder = index + 1
  })
}
