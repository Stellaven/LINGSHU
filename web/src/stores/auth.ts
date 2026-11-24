/**
 * 会话状态（模块级单例，未引入 Pinia 前的轻量方案）
 * ------------------------------------------------------------------
 * 登录态持久化到 localStorage，刷新页面后自动恢复；
 * 登出或 token 失效时清除。路由守卫（src/router/index.ts）依赖本模块。
 * AT 由此模块统一持有：http 层读取/更新（滑动续期、刷新重试），
 * RT 在 HttpOnly Cookie 中，前端代码不接触。
 */

import { computed, reactive } from 'vue'
import type { Session, User } from '@/types/auth'
import * as authApi from '@/api/auth'

const SESSION_KEY = 'llamaindex.auth.session'

function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (raw) return JSON.parse(raw) as Session
  } catch {
    // 损坏的持久化数据按未登录处理
  }
  return null
}

const state = reactive<{ session: Session | null }>({ session: loadSession() })

export const currentUser = computed<User | null>(() => state.session?.user ?? null)
export const isLoggedIn = computed(() => state.session !== null)

/** http 层：读取当前 AT */
export function getAccessToken(): string | null {
  return state.session?.token ?? null
}

/** http 层：静默替换 AT（滑动窗口续期头 / RT刷新 / 改密重签） */
export function setAccessToken(token: string): void {
  if (state.session) {
    state.session.token = token
    persist()
  }
}

/** http 层：token 彻底失效（401 非过期类 / 刷新失败）时清空本地状态 */
export function forceLogout(): void {
  state.session = null
  persist()
}

/** 登录成功后建立会话 */
export async function login(account: string, password: string): Promise<void> {
  state.session = await authApi.login(account, password)
  persist()
}

/** 注册成功后直接建立会话 */
export async function register(account: string, password: string): Promise<void> {
  state.session = await authApi.register(account, password)
  persist()
}

/** 忘记密码：下发验证码（mock 模式返回验证码供页面回显） */
export function requestPasswordCode(account: string): Promise<string> {
  return authApi.requestPasswordCode(account)
}

/** 忘记密码：凭验证码重置密码 */
export function resetPassword(account: string, code: string, newPassword: string): Promise<void> {
  return authApi.resetPassword(account, code, newPassword)
}

/** 修改密码（已登录，需验证原密码；成功后服务端重签令牌） */
export function changePassword(account: string, oldPassword: string, newPassword: string): Promise<void> {
  return authApi.changePassword(account, oldPassword, newPassword)
}

/** 退出登录：通知服务端撤销会话与令牌（幂等），并清空本地状态 */
export async function logout(): Promise<void> {
  await authApi.logout()
  forceLogout()
}

function persist(): void {
  if (state.session) localStorage.setItem(SESSION_KEY, JSON.stringify(state.session))
  else localStorage.removeItem(SESSION_KEY)
}
