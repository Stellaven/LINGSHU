/**
 * HTTP 客户端（fetch 封装）
 * ------------------------------------------------------------------
 * 统一职责（与后端 JWT 技术设计方案 §8/§9 对应）：
 * - 自动携带 Authorization: Bearer <AT>；
 * - 解析统一响应体 { success, code, data, message }；
 * - 仅 code=40102（AT过期）触发静默刷新并重试 1 次，其余 401 一律登出跳登录；
 * - 全局单飞刷新（单例 Promise），避免并发刷新导致 RT 重用误判；
 * - X-New-Access-Token 响应头（滑动窗口续期）：静默替换本地 AT。
 */

/** 后端 API 基础路径（导出供二进制流等不走统一信封的场景使用） */
export const BASE = '/api'

/** 业务错误：code 与后端错误码约定一致（40101~40301） */
export class ApiError extends Error {
  code: number
  status: number

  constructor(message: string, code: number, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  formData?: FormData
  headers?: Record<string, string>
}

interface Envelope<T> {
  success: boolean
  code: number
  data: T
  message: string | null
}

/** 登录/注册/续期接口：不走"401 触发刷新重试"逻辑 */
function isAuthEndpoint(path: string): boolean {
  return path.startsWith('/auth/')
}

/** 全局单例刷新 Promise：并发 40102 时只发起一次 /auth/refresh */
let refreshing: Promise<void> | null = null

function ensureRefreshed(): Promise<void> {
  refreshing ??= performRefresh().finally(() => {
    refreshing = null
  })
  return refreshing
}

/** 兜底通道续期：RT在HttpOnly Cookie中同源自动携带；不走request()避免重试/刷新嵌套 */
async function performRefresh(): Promise<void> {
  const { setAccessToken, forceLogout } = await import('@/stores/auth')
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })
    const envelope = await parseEnvelope<{ access_token: string }>(res)
    if (!res.ok || !envelope.success) throw new Error(envelope.message ?? '刷新失败')
    setAccessToken(envelope.data.access_token)
  } catch {
    // 刷新失败（RT无效/重用/过期）：清空状态，跳登录
    forceLogout()
    window.location.assign('/login')
    throw new ApiError('登录已过期，请重新登录', 40106, 401)
  }
}

async function parseEnvelope<T>(res: Response): Promise<Envelope<T>> {
  try {
    return (await res.json()) as Envelope<T>
  } catch {
    throw new ApiError(`服务异常（${res.status}）`, -1, res.status)
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return doRequest<T>(path, options, 0)
}

async function doRequest<T>(path: string, options: RequestOptions, retried: number): Promise<T> {
  const { getAccessToken, setAccessToken, forceLogout } = await import('@/stores/auth')
  const { method = 'GET', body, formData, headers = {} } = options

  const token = getAccessToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (formData) {
    // FormData 由浏览器自动设置 multipart 边界，禁止手动指定 Content-Type
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
  })

  // 滑动窗口续期：拦截器签发的新AT通过响应头下发，静默替换（§8.1）
  const renewed = res.headers.get('X-New-Access-Token')
  if (renewed) setAccessToken(renewed)

  const envelope = await parseEnvelope<T>(res)

  if (!res.ok || !envelope.success) {
    const code = envelope.code ?? -1
    const message = envelope.message ?? '请求失败'

    // 只有 AT 过期（40102）触发刷新重试，其余 401 一律登出跳登录（§9）
    if (code === 40102 && !isAuthEndpoint(path) && retried < 1) {
      await ensureRefreshed()
      return doRequest<T>(path, options, retried + 1)
    }
    if (res.status === 401 && code !== 40102) {
      forceLogout()
      window.location.assign('/login')
    }
    throw new ApiError(message, code, res.status)
  }

  return envelope.data
}
