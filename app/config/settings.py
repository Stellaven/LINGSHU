import os
from email.policy import default

from pydantic import Field
from pydantic_settings import BaseSettings

ENV = os.getenv('ENV', 'dev')
ENV_FILE = f'.env.{ENV}'

class Settings(BaseSettings):
    model_config = {"env_file": ENV_FILE, "env_file_encoding": "utf-8"}

    PROJECT_NAME: str = Field(default='LlamaIndex学习', description='项目名称')
    POSTGRESQL: str = Field(default=..., description='PG数据库连接')

    # ---------------- 日志 ----------------
    LOG_LEVEL: str = Field(default='INFO', description='根日志器级别（DEBUG/INFO/WARNING/ERROR）')
    LOG_RETENTION_DAYS: int = Field(default=90, description='日志文件保留天数（按天滚动清理）')

    # ---------------- 认证/JWT ----------------
    JWT_SECRET: str = Field(
        default='dev-insecure-jwt-secret-0123456789abcdef',
        description='JWT签名密钥（HS256），生产环境必须通过配置中心下发并支持轮换，禁止使用开发默认值')
    JWT_ALGORITHM: str = Field(default='HS256', description='JWT签名算法')
    AT_TTL: int = Field(default=1800, description='Access Token有效期（秒）')
    RT_SLIDING_TTL: int = Field(default=30 * 24 * 3600, description='Refresh Token滑动有效期（秒）')
    RT_MAX_LIFETIME: int = Field(default=90 * 24 * 3600, description='Refresh Token绝对最大寿命（秒）')
    RENEW_THRESHOLD: int = Field(default=300, description='滑动续期触发阈值：AT剩余有效期低于该值时签发新AT（秒）')
    RT_GRACE: int = Field(default=0, description='RT重用宽限窗口（秒），0为关闭；开启后窗口内二次使用返回同一新RT')
    USER_STATE_CACHE_TTL: int = Field(default=3600, description='用户版本号/状态缓存TTL（秒），改密/禁用时主动失效')
    AUTH_COOKIE_SECURE: bool = Field(default=False, description='RT Cookie是否仅HTTPS传输（生产必须开启）')
    AUTH_COOKIE_PATH: str = Field(default='/', description='RT Cookie路径；经前端代理访问时需与代理路径前缀一致')
    REDIS_URL: str = Field(default='', description='Redis连接（会话/黑名单/RT存储）；留空时降级为进程内存存储，仅限本地开发')

    # ---------------- 密码传输加密（RSA） ----------------
    # 前端用公钥加密密码密文传输，后端用私钥解密后再哈希/校验；
    # 公钥由 GET /auth/public-key 从私钥派生下发，保证密钥对必然配对
    PASSWORD_RSA_PRIVATE_KEY: str = Field(
        default=(
            '-----BEGIN PRIVATE KEY-----\n'
            'MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCuF0D8Os1jAs1v\n'
            'gRY+QrjW7R3QNo8/O/jZ/nuHVqlCK3VZPkcZ7FY5RNnXUoW6sh9S1uiZ8MhUX4Xz\n'
            'WsN+ArU6ECsK0UR41dVzC4964TgK+6H4RMTXUIRFI4hLiVYmR8yEy9FDx6DTQPt6\n'
            'Xd3nXO22yljHGmGwJIngCtGp+KvYzZljfD4J8aKqq57BimBpG+XTbTJdhHALQY3z\n'
            'Rm5a5eAOYpq06GcIXSQE1sepOjnxK4gE+N8AODIB5cSa089s7DiHpoDToINxNjyX\n'
            'AR3Lhqf/uclF1JxYOg9705PjZayzJcO1i6HVlv3aW2XKZR18gSwBIdvBqC8Mh76a\n'
            'Ccfni3VXAgMBAAECggEAEGaEar6nZrJ25BBHJipm+2hvLJRXPl/J+89rl75kR6WM\n'
            'cpHZZOnM3axM0WomywXIyacRVp9GYBx3pAti61YZ+JRZWbWJO9D5QNNP+wWIoBBA\n'
            'nADuglJFg7XrOyJ/CTAuZjxFRJtj3UL77fU12Hv6sQOzBV7I4S0wB/k880RH/C6K\n'
            'XwX5dhTp+NOEamsfO4VSPtB5WpaPkMYCauVhWUZ8breuxaARbnpfJOrOURLugBcM\n'
            'YHA1M5GQpyC/THEWAohqF0yVOl8fw543YrHY+0ous0tJ3Y8k1/WTeASsjWTgFySA\n'
            'kaO0jBm9KDTJwA6dRck7eg5fU8yLhaQ1CvkAKbFEcQKBgQDl47jYtT2JZ9IpYOem\n'
            'HMQE3+PnsTn6wfuAaF+bDLca0ouaZ+JOXJ0oXpt4tZvmF9gP5vYivs5+UBDD20ve\n'
            'H8TZ9s7Kf4dQfCXu4dlc096hD8tc/KWQ482YErKx5zivgd+kEqyTjhXUSd5IOsvp\n'
            'J/VLzoR6AqqoO8s2WHleWB7V2wKBgQDB3SBWpnSSwxP0V/KE8tcu+zgDzuAjNvbO\n'
            'j/f7P+0FNF8bnO6VdJxW5muawNCEUdb5bIUH5T9mNfY9Uc0A0yYERMTy06CyzVd/\n'
            'WA74uyc9XCdDiGqSFbO5xSxNn5GFB0meWE6rb8u+67ZWf2mMYjVpeUaqDXIm8UFw\n'
            'KG9cGNw9NQKBgF9hTxUihUiYObsPSK1D7BQ1rEI55ttiVm3dYCVdbi8DwgYrKdrn\n'
            'VBEmx4yalPcvV2appd+emOARahNIzj53od3pJ70ekk7TY42sSNnZ0dmzSuXmsO7f\n'
            'hTKeN2PWkk9HLDnPwahq4CW3DDGdq3KuMHjmU1Kn/pRUUqjWpmx9VTXXAoGAbEra\n'
            'oqyvF8BzKB3sskl43JymqLHqUKGGctLHQoluHGcp7aHXQJN4Na7XUwX8NL4GqSPu\n'
            'l/9+T9k66PwF2T0Z0m6b2c1PyjGce90z18ur2sHciQPuDBalY9N5sQ6+2iG9BP/t\n'
            'SiTUGp1PKLhZvHqrvXRqfdmu94Py+vULZ9XXSTUCgYEAiP7NsNQ+R59/w3E4TgpV\n'
            'SGkFfMFXvodqcVI9KvkwnNwEjx6ZKlzOKNhuAtE1G06rws3PWiNxzYIyLiyVNz/1\n'
            'dxXNyrn+fwugnehCfPzeLtPb+NZ9ZTviMmFNL9BP8CIr3b6yGahhthJNaYbk8YmV\n'
            'JB/fBqzt9DdOkOLWTN50hPE=\n'
            '-----END PRIVATE KEY-----\n'
        ),
        description='密码传输RSA解密私钥（PKCS#8 PEM，2048bit）；生产环境必须通过配置下发并定期轮换，禁止使用开发默认值')

    # ---------------- 登录防暴力破解 ----------------
    LOGIN_MAX_FAILS: int = Field(default=5, description='同一账号连续登录失败N次后锁定账号')
    LOGIN_LOCK_TTL: int = Field(default=30 * 60, description='账号锁定时长（秒）；失败计数窗口与锁定时长一致')

    # ---------------- 文件处理任务 ----------------
    TASK_BACKEND: str = Field(default='bullmq', description='任务框架后端：bullmq（Redis队列）/ inline（进程内直执行）；REDIS_URL未配置时自动降级inline')
    TASK_CONCURRENCY: int = Field(default=2, description='应用内任务并发消费数')
    TASK_MAX_ATTEMPTS: int = Field(default=3, description='任务失败自动重试次数（指数退避）')
    TASK_BACKOFF_DELAY: int = Field(default=2000, description='任务重试指数退避基础延迟（毫秒）')
    TASK_KEEP_FAILED: int = Field(default=500, description='失败任务保留最近N条便于排障')

    # ---------------- MinIO 对象存储 ----------------
    MINIO_ENDPOINT: str = Field(default='localhost:9000', description='MinIO服务地址（本地启动默认localhost:9000）')
    MINIO_ACCESS_KEY: str = Field(default='minioadmin', description='MinIO访问密钥（本地默认minioadmin）')
    MINIO_SECRET_KEY: str = Field(default='minioadmin', description='MinIO秘密密钥（本地默认minioadmin）')
    MINIO_BUCKET: str = Field(default='lingshu', description='存储桶名（不存在时自动创建）')
    MINIO_SECURE: bool = Field(default=False, description='是否HTTPS访问（本地MinIO为False）')

    # ---------------- Docling 解析服务 ----------------
    DOCLING_BASE_URL: str = Field(
        default='http://localhost:5001',
        description='docling-serve服务地址（本地部署默认5001端口）；文件处理策略parser=Docling时使用')
    DOCLING_TIMEOUT: float = Field(
        default=300.0,
        description='Docling解析请求超时（秒）；OCR/大文档解析耗时较长，默认5分钟')
    DOCLING_CONNECT_TIMEOUT: float = Field(
        default=10.0,
        description='Docling解析连接超时（秒）；服务冷启动较慢，单独放宽')

    # ---------------- 向量数据库（Milvus） ----------------
    MILVUS_URI: str = Field(
        default='http://localhost:19530',
        description='Milvus服务地址（本地standalone默认19530端口）；也可配置本地.db文件走milvus-lite')
    MILVUS_DIM: int = Field(default=1024, description='向量维度（bge-m3为1024），仅首次创建collection时使用')
    RETRIEVAL_TOP_K: int = Field(default=20, description='向量相似度检索默认返回条数')

    # ---------------- 全文检索（Elasticsearch） ----------------
    ES_URL: str = Field(
        default='http://localhost:9200',
        description='Elasticsearch服务地址；分块全文检索（每个知识库一个索引 kb_{kb_id}）')
    ES_USERNAME: str = Field(default='', description='Elasticsearch用户名（未启用认证时留空）')
    ES_PASSWORD: str = Field(default='', description='Elasticsearch密码（未启用认证时留空）')
    ES_REQUEST_TIMEOUT: float = Field(default=60.0, description='Elasticsearch请求超时（秒）')

    # ---------------- 模型服务（OpenAI兼容协议） ----------------
    MODEL_CONNECT_TIMEOUT: float = Field(default=10.0, description='模型服务连接超时（秒）；连接慢的私有网关可放宽')
    MODEL_READ_TIMEOUT: float = Field(default=20.0, description='模型目录拉取读取超时（秒）')
    MODEL_REQUEST_TIMEOUT: float = Field(default=60.0, description='模型推理请求（rerank等）整体超时（秒）')

    # ---------------- 知识图谱（OpenSPG/KAG） ----------------
    KAG_OPENSPG_URL: str = Field(
        default='http://localhost:8887',
        description='OpenSPG(KAG)引擎地址；策略graph=True时构建图谱（每个知识库对应一个KAG项目 kb_{kb_id}）')
    KAG_NEO4J_URI: str = Field(
        default='neo4j://release-openspg-neo4j:7687',
        description='KAG创建项目时写入vectorizer/graph_store config的Neo4j地址（KAG服务端可达）')
    KAG_NEO4J_USER: str = Field(default='neo4j', description='KAG后端Neo4j用户名')
    KAG_NEO4J_PASSWORD: str = Field(default='neo4j@openspg', description='KAG后端Neo4j密码；生产环境必须通过配置下发')
    KAG_EMBEDDING_BASE_URL: str = Field(
        default='http://host.docker.internal:11434/v1',
        description='KAG项目vectorizer的embedding服务地址（OpenAI兼容，KAG服务端容器可达）')
    KAG_EMBEDDING_MODEL: str = Field(default='bge-m3:latest', description='KAG项目vectorizer模型名')
    KAG_EMBEDDING_MODEL_ID: str = Field(
        default='9ec07a0c0be2491d9d272d2d8cae547c@bge-m3:latest',
        description='KAG服务端已注册的vectorizer模型ID（须与服务端注册记录一致）')


settings = Settings()