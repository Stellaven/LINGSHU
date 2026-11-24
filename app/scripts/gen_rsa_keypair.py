"""生成密码传输加密用的RSA密钥对（2048bit，PKCS#8）

用法：
    python scripts/gen_rsa_keypair.py

输出 .env 可直接粘贴的配置项：
    PASSWORD_RSA_PRIVATE_KEY  → 后端 .env.{ENV}（私钥，务必保密，支持轮换）
公钥无需单独配置：后端 GET /auth/public-key 从私钥自动派生下发。
"""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    single_line = private_pem.replace('\n', '\\n').strip()
    print('# 后端 .env.{ENV} 追加（单行转义写法，\\n为字面量）：')
    print(f"PASSWORD_RSA_PRIVATE_KEY='{single_line}'")
    print()
    print('# PEM 原文（便于核对/入库配置中心）：')
    print(private_pem)


if __name__ == '__main__':
    main()
