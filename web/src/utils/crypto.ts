/**
 * 密码传输加密（RSA）
 * ------------------------------------------------------------------
 * 约定与后端 modules/auth/rsa_cipher.py 对应：
 * - 公钥由后端 GET /api/auth/public-key 下发（从私钥派生，保证配对）；
 * - 前端用公钥对密码做 RSAES-PKCS1-v1_5 加密（jsencrypt），base64 密文入 body；
 * - 私钥只在后端，前端永不接触；公钥非敏感，可缓存整个会话周期；
 * - 登录/注册/修改密码三个接口的密码字段都必须先经 encryptPassword 处理。
 */

import JSEncrypt from 'jsencrypt'
import { ApiError, request } from '@/api/http'

/** 会话级缓存：模块级变量，刷新页面后重新获取（公钥可公开，无过期问题） */
let cachedPublicKey = ''

async function getPublicKey(): Promise<string> {
  if (cachedPublicKey) return cachedPublicKey
  const data = await request<{ public_key: string }>('/auth/public-key')
  if (!data.public_key) throw new ApiError('获取密码加密公钥失败', 40006, 400)
  cachedPublicKey = data.public_key
  return cachedPublicKey
}

/** 密码明文 → base64 RSA 密文；失败抛业务错误由表单统一提示 */
export async function encryptPassword(plain: string): Promise<string> {
  const publicKey = await getPublicKey()
  const encryptor = new JSEncrypt()
  encryptor.setPublicKey(publicKey)
  const ciphertext = encryptor.encrypt(plain)
  if (!ciphertext) throw new ApiError('密码加密失败，请重试', 40006, 400)
  return ciphertext
}
