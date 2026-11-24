/**
 * 认证模块 API 层（已接入后端 /auth/*）
 * ------------------------------------------------------------------
 * 后端接口（JWT 登录与令牌生命周期管理技术设计方案 §6）：
 *   POST /api/auth/register   注册  body: { account, password } → { id, account, created_at }
 *   POST /api/auth/login      登录  body: { account, password, device_id? } → { access_token, expires_in, token_type, user }
 *   POST /api/auth/refresh    续期  RT 走 HttpOnly Cookie → { access_token, expires_in, user }
 *   POST /api/auth/logout     退出  Header: Authorization（幂等）
 *   POST /api/auth/password   改密  Header: Authorization, body: { oldPassword, newPassword }（RSA密文）→ 签发新令牌
 *
 * 安全约定：AT 走 Authorization 头并由前端持久化；RT 仅在 HttpOnly Cookie
 * 中流转，前端代码不可见（禁止存 localStorage / 出现在 URL / 打日志）。
 * 密码明文不出前端：登录/注册/改密提交前经 utils/crypto encryptPassword
 * 用后端下发的公钥做 RSA 加密，后端解密后再哈希/校验。
 * 忘记密码（验证码通道）后端暂未实现，见 requestPasswordCode / resetPassword。
 */

import type { Session, User } from '@/types/auth'
import { ApiError, request } from '@/api/http'
import { encryptPassword } from '@/utils/crypto'

interface TokenResponse {
  access_token: string
  expires_in: number
  token_type: string
  user: { id: string; account: string; created_at: string | null }
}

function toUser(u: TokenResponse['user']): User {
  return { id: u.id, account: u.account, createdAt: u.created_at ?? '' }
}

function toSession(res: TokenResponse): Session {
  return { token: res.access_token, user: toUser(res.user) }
}

/** ---------------- 认证 ---------------- */

/** POST /api/auth/register  body: { account, password: RSA密文 }（注册成功后自动登录建会话） */
export async function register(account: string, password: string): Promise<Session> {
  const encrypted = await encryptPassword(password)
  await request('/auth/register', { method: 'POST', body: { account, password: encrypted } })
  return login(account, password)
}

/** POST /api/auth/login  body: { account, password: RSA密文 } */
export async function login(account: string, password: string): Promise<Session> {
  const encrypted = await encryptPassword(password)
  const data = await request<TokenResponse>('/auth/login', { method: 'POST', body: { account, password: encrypted } })
  return toSession(data)
}

/** POST /api/auth/refresh 由 http 层在 40102 时内部调用（RT 走 Cookie，前端无需主动发起） */

/** POST /api/auth/logout  Header: Authorization（幂等，失败不阻断本地登出） */
export async function logout(): Promise<void> {
  try {
    await request('/auth/logout', { method: 'POST' })
  } catch {
    // 后端已不可达/令牌已失效也视为登出成功
  }
}

/** POST /api/auth/password  body: { oldPassword, newPassword }（RSA密文），成功后签发新令牌 */
export async function changePassword(_account: string, oldPassword: string, newPassword: string): Promise<void> {
  const [oldEncrypted, newEncrypted] = await Promise.all([
    encryptPassword(oldPassword),
    encryptPassword(newPassword),
  ])
  const data = await request<TokenResponse>('/auth/password', {
    method: 'POST',
    body: { oldPassword: oldEncrypted, newPassword: newEncrypted },
  })
  const { setAccessToken } = await import('@/stores/auth')
  setAccessToken(data.access_token)
}

/** ---------------- 忘记密码（后端暂未实现，保留 mock 演示流程） ----------------
 * TODO(backend): 验证码依赖邮件/短信通道，落地时新增
 *   POST /api/auth/password-code  body: { account }
 *   POST /api/auth/reset-password body: { account, code, newPassword }
 */

/** mock 验证码状态：account → { code, expiresAt }（真实后端校验，前端仅透传） */
const issuedCodes = new Map<string, { code: string; expiresAt: number }>()
const CODE_TTL_MS = 5 * 60 * 1000

/** mock：无邮件/短信通道，将验证码直接返回给页面回显（仅演示用） */
export async function requestPasswordCode(account: string): Promise<string> {
  await new Promise((resolve) => setTimeout(resolve, 500))
  if (account.trim() !== 'demo') throw new ApiError('该账号尚未注册', 40004, 400)
  const code = String(Math.floor(100000 + Math.random() * 900000))
  issuedCodes.set(account.trim(), { code, expiresAt: Date.now() + CODE_TTL_MS })
  return code
}

/** mock：凭验证码重置密码（后端验证码通道未实现，密码不实际变更） */
export async function resetPassword(account: string, code: string, _newPassword: string): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 500))
  const issued = issuedCodes.get(account.trim())
  if (!issued || issued.code !== code.trim()) throw new ApiError('验证码错误', 40005, 400)
  if (Date.now() > issued.expiresAt) throw new ApiError('验证码已过期，请重新获取', 40005, 400)
  issuedCodes.delete(account.trim())
}
