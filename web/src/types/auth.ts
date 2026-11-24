/** 认证模块类型定义 */

/** 用户公开信息（不含凭据） */
export interface User {
  id: string
  account: string
  createdAt: string
}

/** 登录态：token + 用户信息 */
export interface Session {
  token: string
  user: User
}
