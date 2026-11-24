"""认证模块常量：错误码、存储Key前缀、Cookie名"""

# ---------------- 业务错误码（与技术设计方案 §9 对应） ----------------
CODE_OK = 0                    # 成功
CODE_TOKEN_INVALID = 40101     # AT签名/格式错误 → 跳登录
CODE_TOKEN_EXPIRED = 40102     # AT过期 → 调 /auth/refresh
CODE_TOKEN_REVOKED = 40103     # 已登出/黑名单 → 跳登录
CODE_SESSION_REVOKED = 40104   # 会话失效 → 跳登录
CODE_TOKEN_VERSION_MISMATCH = 40105  # 版本号不符（改密后旧令牌）→ 跳登录
CODE_REFRESH_TOKEN_INVALID = 40106   # RT无效/重用 → 跳登录
CODE_USER_DISABLED = 40301     # 账号禁用 → 提示（HTTP 403）
CODE_PASSWORD_DECRYPT_FAILED = 40006  # 密码密文解密失败/明文长度不符（前端加密版本不匹配）→ 提示（HTTP 400）
CODE_ACCOUNT_LOCKED = 42901    # 连续登录失败触发防暴力破解锁定 → 提示剩余时间（HTTP 429）

# ---------------- 存储Key前缀（与技术设计方案 §5.2 对应） ----------------
KEY_SESSION = 'auth:session:{sid}'        # 登录会话
KEY_RT = 'auth:rt:{token_hash}'           # RT记录（服务端只存哈希）
KEY_BLACKLIST = 'auth:blacklist:{jti}'    # AT黑名单，TTL=AT剩余有效期
KEY_USER_TV = 'auth:user_tv:{user_id}'    # 用户token_version缓存
KEY_FAMILY = 'auth:family:{family_id}'    # RT轮换族索引（成员为RT哈希）
KEY_USER_SESSIONS = 'auth:user_sessions:{user_id}'  # 用户全部会话索引（成员为sid）
KEY_GRACE = 'auth:grace:{token_hash}'     # RT重用宽限窗口内的新RT（默认关闭）
KEY_LOGIN_FAIL = 'auth:login_fail:{account}'   # 登录连续失败计数（防暴力破解）
KEY_LOGIN_LOCK = 'auth:login_lock:{account}'   # 登录锁定标记（值为锁定到期时间戳）

RT_COOKIE_NAME = 'rt'
NEW_AT_HEADER = 'X-New-Access-Token'
NEW_AT_EXPIRES_HEADER = 'X-New-Access-Token-Expires-In'
