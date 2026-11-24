"""令牌与密码安全工具：JWT签发/校验、RT生成/哈希、密码加盐哈希

安全约束（设计方案 §10）：
- JWT密钥走配置（settings.JWT_SECRET），禁止硬编码；
- RT为256bit随机数，服务端只存SHA-256，日志禁止打印明文；
- AT不放入敏感信息（手机号、权限明细等）。
"""

import hashlib
import hmac
import secrets
import time
import uuid
from typing import Any, Optional

import jwt

from config.settings import settings
from core.exceptions import BusinessError
from modules.auth.constants import CODE_TOKEN_EXPIRED, CODE_TOKEN_INVALID

# pbkdf2参数：迭代次数可随硬件水平上调，旧哈希校验时按存储值解析
_PBKDF2_ITERATIONS = 120_000
_PBKDF2_ALGO = 'pbkdf2_sha256'


# ---------------- 密码哈希（标准库实现，无需额外依赖） ----------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, _PBKDF2_ITERATIONS)
    return f'{_PBKDF2_ALGO}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}'


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split('$')
        if algo != _PBKDF2_ALGO:
            return False
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), int(iterations))
        # hmac.compare_digest防时序攻击
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


# ---------------- Access Token（JWT） ----------------
def create_access_token(user_id: int, sid: str, token_version: int, ttl: Optional[int] = None) -> str:
    """签发AT：必需声明 sub/jti/sid/token_version/iat/exp（设计方案 §4.1）"""
    now = int(time.time())
    payload = {
        'sub': str(user_id),
        'jti': uuid.uuid4().hex,
        'sid': sid,
        'token_version': token_version,
        'iat': now,
        'exp': now + (ttl if ttl is not None else settings.AT_TTL),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """校验并解码AT。签名/格式错误 → 40101，过期 → 40102（客户端据此触发RT续期）"""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise BusinessError('登录已过期，请重新登录', code=CODE_TOKEN_EXPIRED) from e
    except jwt.PyJWTError as e:
        raise BusinessError('令牌无效，请重新登录', code=CODE_TOKEN_INVALID) from e


# ---------------- Refresh Token（随机字符串） ----------------
def create_refresh_token() -> str:
    """256bit熵的随机字符串（base64url，无需padding）"""
    return secrets.token_urlsafe(32)


def hash_refresh_token(rt: str) -> str:
    """服务端只存SHA-256(rt)，不存明文"""
    return hashlib.sha256(rt.encode()).hexdigest()
