# ---------------------- SQLAlchemy ORM Model ----------------------
from sqlalchemy import Column, Text, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB

from db.pg.pg_manager import Base


# ---------------------- 用户 ----------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 登录账号（唯一）
    account = Column(Text, nullable=False, unique=True)
    # 密码哈希（pbkdf2_hmac，格式：salt$hash，十六进制）
    password_hash = Column(Text, nullable=False)
    # 令牌版本号：改密时自增，用于全端令牌失效
    token_version = Column(Integer, nullable=False, default=1)
    # 状态：1正常 0禁用
    status = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------- Refresh Token 审计 ----------------------
class AuthRefreshToken(Base):
    """RT审计表：主数据在Redis（内存/Redis存储层），本表用于审计与排障"""
    __tablename__ = "auth_refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # SHA-256(rt) 十六进制
    token_hash = Column(Text, nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 会话ID：一次登录对应一个会话
    sid = Column(Text, nullable=False, index=True)
    # RT轮换族ID：同一会话轮换出的RT同族
    family_id = Column(Text, nullable=False, index=True)
    # 状态：1active 2used 3revoked
    status = Column(Integer, nullable=False, default=1)
    # 轮换后替代本RT的新RT哈希
    replaced_by = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)


class LlamaDocstoreNode(Base):
    __tablename__ = "llama_docstore_nodes"

    node_id = Column(Text, primary_key=True)
    # 可空：无SOURCE关系的节点（如Document本身）ref_doc_id为NULL
    ref_doc_id = Column(Text, nullable=True, index=True)
    # 节点hash，IngestionPipeline去重（set/get_document_hash）使用
    doc_hash = Column(Text, nullable=True, index=True)
    # node本体JSON（doc_to_json格式）；store_text=False时为NULL
    node_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------- 文件解析策略配置 ----------------------
class FileParseStrategy(Base):
    """知识库维度的文件处理策略，可被库内多条文档引用"""
    __tablename__ = "file_parse_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 所属知识库
    kb_id = Column(Integer, ForeignKey("project_knowledge_bases.id"), nullable=False, index=True)
    # 策略名称（知识库内唯一）
    strategy_name = Column(Text, nullable=False)
    # 嵌入模型（项目模型实例下的 embedding 模型名）
    embed_model = Column(Text, nullable=False, default="bge-m3")
    # 编排序列：解析 → 前置(文档级)提取 → 分块(可级联) → 后置(块级)提取，
    # 每个提取器条目独立携带执行LLM；执行顺序即 transformations 顺序
    stages = Column(JSONB, nullable=False,
                    default=lambda: {"parser": [], "pre_extract": [], "split": [], "post_extract": []})
    # 图谱构建约束（graph开启时生效）：{"entityTypes":[...],"relationTypes":[{"name","source","target"}]}
    graph_config = Column(JSONB, nullable=True)
    # 是否构建图谱
    graph = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint('kb_id', 'strategy_name', name='uq_kb_strategy_name'),)


# ---------------------- 知识库图谱 Schema ----------------------
class KbGraphSchema(Base):
    """知识库维度的图谱schema（每库一份）：实体/关系类型定义，构图时注册到KAG项目SPG schema

    策略开启构建图谱（graph=True）时要求本表已有对应记录，策略本身不可修改schema。
    """
    __tablename__ = "kb_graph_schemas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 所属知识库（每库一份schema）
    kb_id = Column(Integer, ForeignKey("project_knowledge_bases.id"), nullable=False, unique=True)
    # 图谱schema定义：{"entities":[{"name","desc","properties":{}}],
    #                  "relations":[{"name","desc","subjectType","objectType"}]}
    schema = Column("schema", JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------- 知识库文件 ----------------------
class KbFile(Base):
    """知识库内上传的文件：MinIO存对象，本表存元数据与解析状态"""
    __tablename__ = "kb_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 所属知识库
    kb_id = Column(Integer, ForeignKey("project_knowledge_bases.id"), nullable=False, index=True)
    # 原始文件名（含扩展名）
    file_name = Column(Text, nullable=False)
    # MinIO对象key（uploads/yyyyMMdd/uuid.ext）
    object_name = Column(Text, nullable=False)
    # 存储桶
    bucket = Column(Text, nullable=False)
    # 文件大小（字节）
    size = Column(Integer, nullable=False)
    # MIME类型
    content_type = Column(Text, nullable=False, default='')
    # 处理策略（未选择策略时为空，按文件后缀默认切分）
    strategy_id = Column(Integer, ForeignKey("file_parse_strategies.id"), nullable=True, index=True)
    # 解析状态：processing 索引中 / indexed 已索引 / failed 失败
    status = Column(Text, nullable=False, default='processing')
    # 分块数量（解析完成后回写）
    chunk_count = Column(Integer, nullable=True)
    # 解析失败原因
    error = Column(Text, nullable=True)
    # 上传人
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------- 知识库配置 ----------------------
class KnowledgeBaseConfig(Base):
    __tablename__ = "knowledge_base_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 知识库名
    name = Column(Text, nullable=False, unique=True)
    # 知识库描述
    description = Column(Text, nullable=True)
    # 向量模型
    embed_model = Column(Text, nullable=False, default="bge-m3")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------- 团队 ----------------------
class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False, server_default='')
    # 创建者（创建时自动写入team_members所有者记录，冗余本字段便于追溯）
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------- 团队成员 ----------------------
class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 登录账号（冗余存储，展示与检索免联表）
    account = Column(Text, nullable=False)
    # 团队内昵称（默认取账号）
    nickname = Column(Text, nullable=False)
    # 身份：owner / member
    role = Column(Text, nullable=False, default='member')
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('team_id', 'user_id', name='uq_team_member'),)


# ---------------------- 团队项目 ----------------------
class TeamProject(Base):
    __tablename__ = "team_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False, server_default='')
    # 项目负责人
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 自定义排序值（越小越靠前，同团队内递增）
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------- 项目成员 ----------------------
class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("team_projects.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account = Column(Text, nullable=False)
    nickname = Column(Text, nullable=False)
    # 身份：owner / member
    role = Column(Text, nullable=False, default='member')
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('project_id', 'user_id', name='uq_project_member'),)


# ---------------------- 项目知识库 ----------------------
class ProjectKnowledgeBase(Base):
    __tablename__ = "project_knowledge_bases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("team_projects.id"), nullable=False, index=True)
    # 知识库名（项目内唯一）
    name = Column(Text, nullable=False)
    # 知识库描述
    description = Column(Text, nullable=False, server_default='')
    # 向量模型
    embed_model = Column(Text, nullable=False, default="bge-m3")
    # KAG(OpenSPG)项目ID（策略graph=True首次构图时懒创建，与Milvus collection/ES索引一一对应）
    kag_project_id = Column(Integer, nullable=True)
    # 项目内自定义排序值（越小越靠前）
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint('project_id', 'name', name='uq_project_kb_name'),)


# ---------------------- 模型提供商配置 ----------------------
class ModelProvider(Base):
    __tablename__ = "model_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 提供商名：DeepSeek、OpenAI...
    name = Column(Text, nullable=False, unique=True)
    # 所属区域：global 国际 / china 国内
    region = Column(Text, nullable=False, default='global')
    # 品牌色（无LOGO时的回退头像底色，前端展示用）
    color = Column(Text, nullable=False, default='')
    # 厂商LOGO静态资源路径（如 /provider-logos/openai.svg；空串时回退首字母图标）
    logo = Column(Text, nullable=False, default='')
    # 官方默认 API Base URL（实例未自定义时使用，仅作展示占位）
    default_base_url = Column(Text, nullable=False, default='')
    # 是否启用该提供商
    enabled = Column(Boolean, nullable=False, default=False)
    # 展示排序（越小越靠前）
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------- 模型实例配置 ----------------------
class ModelInstance(Base):
    __tablename__ = "model_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 所属项目（项目内模型配置实例；为空表示历史/全局实例）
    project_id = Column(Integer, ForeignKey("team_projects.id"), nullable=True, index=True)
    # 所属模型提供商ID
    provider_id = Column(Integer, ForeignKey("model_providers.id"), nullable=False, index=True)
    # 实例名
    name = Column(Text, nullable=False)
    # API Key
    api_key = Column(Text, nullable=False)
    # Base URL
    base_url = Column(Text, nullable=False)
    # 是否在所属项目内启用
    enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------------------- 模型配置 ----------------------
class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 所属模型实例ID
    instance_id = Column(Integer, ForeignKey("model_instances.id"), nullable=False, index=True)
    # 模型名称：deepseek-chat、bge-m3...
    name = Column(Text, nullable=False)
    # 模型类型：chat / embedding / rerank...（测试连接未识别时为空，可手动编辑）
    model_type = Column(Text, nullable=True)
    # 最大上下文长度（未填写时为空，可手动编辑）
    max_context_length = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())