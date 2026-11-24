"""密码传输加密（RSA）：前端公钥加密密文，后端私钥解密还原明文

安全约束：
- 私钥仅存配置（settings.PASSWORD_RSA_PRIVATE_KEY），禁止入日志/响应；
- 公钥由私钥派生后经 GET /auth/public-key 下发，保证密钥对必然配对；
- 填充方式与前端 jsencrypt 对齐：RSAES-PKCS1-v1_5（2048bit，单块最长245字节明文）；
- 解密失败统一抛业务异常，不区分失败原因（避免给攻击者探测信息）。
"""

import base64
import threading

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from config.settings import settings
from core.exceptions import BusinessError
from modules.auth.constants import CODE_PASSWORD_DECRYPT_FAILED

_PASSWORD_MAX_LEN = 64  # 与原schema明文约束一致：解密后仍需校验长度

_lock = threading.Lock()
_private_key: rsa.RSAPrivateKey | None = None
_public_key_pem: str | None = None


def _load_private_key() -> rsa.RSAPrivateKey:
    """惰性加载并缓存私钥；兼容单行转义（.env中\\n）与真实换行两种PEM写法"""
    global _private_key
    if _private_key is None:
        with _lock:
            if _private_key is None:
                raw = settings.PASSWORD_RSA_PRIVATE_KEY
                if '\\n' in raw:
                    raw = raw.replace('\\n', '\n')
                try:
                    key = load_pem_private_key(raw.encode(), password=None)
                except (ValueError, TypeError) as e:
                    raise RuntimeError('PASSWORD_RSA_PRIVATE_KEY 配置无效，无法解析PEM私钥') from e
                if not isinstance(key, rsa.RSAPrivateKey):
                    raise RuntimeError('PASSWORD_RSA_PRIVATE_KEY 必须是RSA私钥')
                _private_key = key
    return _private_key


def get_public_key_pem() -> str:
    """从私钥派生公钥并缓存，供 /auth/public-key 下发（SPKI格式PEM）"""
    global _public_key_pem
    if _public_key_pem is None:
        public_key = _load_private_key().public_key()
        _public_key_pem = public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
    return _public_key_pem


def decrypt_password(ciphertext_b64: str, min_length: int = 1) -> str:
    """解密前端传来的密码密文（base64 RSA密文），并校验明文长度

    失败（非法base64/密文长度不符/填充错误/明文超长）统一抛40006，
    提示语与"账号或密码错误"同等模糊，不泄露具体失败原因。
    """
    try:
        ciphertext = base64.b64decode(ciphertext_b64, validate=True)
        if len(ciphertext) != (_load_private_key().key_size + 7) // 8:
            raise ValueError('密文长度与密钥规模不符')
        plaintext = _load_private_key().decrypt(ciphertext, padding.PKCS1v15()).decode('utf-8')
    except (ValueError, TypeError, UnicodeDecodeError) as e:
        raise BusinessError('密码解密失败，请刷新页面后重试', code=CODE_PASSWORD_DECRYPT_FAILED, status_code=400) from e
    if not (min_length <= len(plaintext) <= _PASSWORD_MAX_LEN):
        raise BusinessError('密码长度需在6~64位之间' if min_length > 1 else '密码长度需在1~64位之间',
                        code=CODE_PASSWORD_DECRYPT_FAILED, status_code=400)
    return plaintext
