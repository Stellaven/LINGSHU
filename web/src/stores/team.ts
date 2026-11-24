/**
 * 团队状态（模块级单例，未引入 Pinia 前的轻量方案）
 * ------------------------------------------------------------------
 * 侧边栏「我的团队」数据源：首次进入业务页时拉取；
 * 新建/更新/解散/退出/移交后同步维护列表与「我的角色」映射。
 */

import { computed, reactive } from 'vue'
import type { Team, TeamRole } from '@/types/team'
import * as teamApi from '@/api/team'
import { currentUser } from '@/stores/auth'

const state = reactive<{
  teams: Team[]
  /** teamId → 我在该团队中的角色 */
  roles: Record<string, TeamRole>
  selectedId: string | null
  loaded: boolean
  loading: boolean
}>({ teams: [], roles: {}, selectedId: null, loaded: false, loading: false })

/** 当前列表所属的登录账号；切换账号后需重新拉取，避免显示上一个账号的团队 */
let loadedFor: string | null = null

export const teams = computed(() => state.teams)
export const loaded = computed(() => state.loaded)
export const selectedTeam = computed(
  () => state.teams.find((t) => t.id === state.selectedId) ?? null,
)

/** 我在某团队中的角色（列表未加载时按成员兜底） */
export function myRole(teamId: string): TeamRole {
  return state.roles[teamId] ?? 'member'
}

/** 首次调用时拉取团队列表（重复调用/同账号不重复请求；账号切换后重新拉取） */
export async function ensureTeams(): Promise<void> {
  const account = currentUser.value?.account
  if (!account) return
  if (state.loading) return
  if (state.loaded && loadedFor === account) return
  state.loading = true
  try {
    const switched = loadedFor !== account
    const list = await teamApi.listTeams()
    state.teams = list.map((t) => ({
      id: t.id,
      name: t.name,
      description: t.description,
      createdAt: t.createdAt,
    }))
    state.roles = Object.fromEntries(list.map((t) => [t.id, t.myRole]))
    state.loaded = true
    loadedFor = account
    if (switched) state.selectedId = null
    if (!state.selectedId && state.teams.length) state.selectedId = state.teams[0].id
  } finally {
    state.loading = false
  }
}

/** 选中某个团队 */
export function selectTeam(id: string): void {
  state.selectedId = id
}

/** 新建团队：成功后追加到列表末尾并选中（创建者为所有者） */
export async function createTeam(name: string, description = ''): Promise<Team> {
  const team = await teamApi.createTeam(name, description)
  state.teams.push(team)
  state.roles[team.id] = 'owner'
  state.selectedId = team.id
  return team
}

/** 更新团队基础信息 */
export async function updateTeam(
  teamId: string,
  patch: { name?: string; description?: string },
): Promise<void> {
  const team = await teamApi.updateTeam(teamId, patch)
  const index = state.teams.findIndex((t) => t.id === teamId)
  if (index >= 0) state.teams[index] = team
}

/** 从本地列表移除团队；若当前选中则切换到剩余第一个 */
function removeFromList(teamId: string): void {
  state.teams = state.teams.filter((t) => t.id !== teamId)
  delete state.roles[teamId]
  if (state.selectedId === teamId) state.selectedId = state.teams[0]?.id ?? null
}

/** 解散团队（所有者） */
export async function deleteTeam(teamId: string): Promise<void> {
  await teamApi.deleteTeam(teamId)
  removeFromList(teamId)
}

/** 退出团队（成员） */
export async function leaveTeam(teamId: string): Promise<void> {
  await teamApi.leaveTeam(teamId)
  removeFromList(teamId)
}

/** 移交所有权：我的角色变为成员 */
export async function transferOwnership(teamId: string, memberId: string): Promise<void> {
  await teamApi.transferOwnership(teamId, memberId)
  state.roles[teamId] = 'member'
}
