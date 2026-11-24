"""KAG(OpenSPG) 图谱存储封装：与 es_store/milvus_store 并列，供 service 层调用

对应关系约定：应用知识库 ↔ KAG项目(namespace=Kb{kb_id}) ↔ Milvus collection ↔ ES索引。
（KAG项目命名受服务端规范约束：^[A-Z][A-Za-z0-9]{0,15}$，Neo4j库名由其小写推导、
不允许下划线，故与Milvus/ES的命名是各自独立生成的）

- ensure_project(kb_id)：懒创建 KAG 项目并回写 kb 表 kag_project_id（首次构图时调用）
- build_graph：把切分节点转成 KAG Chunk，复用 KAG SchemaFreeExtractor 抽取
  （NER→实体标准化→三元组抽取，chunk 与实体间自动建 source 互索引边），
  经 KGWriter→SPGServer 写入 Neo4j；label 自动加项目 namespace 前缀
- delete_file_graph：按 chunk 节点ID删除该文件的图数据（实体节点跨文件共享，不删）
- drop_project：删除项目（OpenSPG REST 无删除端点，当前仅告警提示手动清理）

兼容性约束（验证结论）：
- 进程内任何 protobuf import 前须设置 PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python（main.py 顶部已设）
- 禁止 `import kag` 全量包（其 __init__ 会拉起 solver→mcp，与新版 pydantic 不兼容），一律子模块导入
- KAG 配置经环境变量全局生效，并发任务会串库：所有 KAG 操作持模块级锁串行执行
"""

import asyncio
import logging
import os
import re
import threading

from sqlalchemy import select

from config.settings import settings
from core.dependencies import get_db_session
from db.pg.orm_models import LlamaDocstoreNode, ProjectKnowledgeBase

# 兜底：若调用方未经过 main.py（如脚本直接import本模块）
os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')

log = logging.getLogger(__name__)

# KAG 配置按环境变量全局生效（KAG_PROJECT_ID/KAG_PROJECT_HOST_ADDR + KAG_CONFIG），
# 进程内多知识库并发处理会互相污染，所有 KAG 操作串行化
_kag_lock = threading.RLock()


def chunk_namespace(kb_id: int) -> str:
    """知识库对应的 KAG 项目 namespace（服务端规范：^[A-Z][A-Za-z0-9]{0,15}$；
    Neo4j库名由其小写推导，不允许下划线，故不能用 kb_{kb_id} 形式）"""
    return f'Kb{kb_id}'


def _ensure_kag_env(kag_project_id: int) -> None:
    """按目标项目设置 KAG 全局配置（须在持锁状态下调用）"""
    os.environ['KAG_PROJECT_ID'] = str(kag_project_id)
    os.environ['KAG_PROJECT_HOST_ADDR'] = settings.KAG_OPENSPG_URL
    # KAG_CONFIG 缓存项目配置（namespace/host_addr等），切项目后必须重新初始化（从服务端拉取）
    from kag.common.conf import KAG_CONFIG
    KAG_CONFIG.initialize(prod=True)


async def get_project(kb_id: int) -> int | None:
    """读取知识库已登记的 KAG 项目ID（未建图返回None，不创建）"""
    async with get_db_session() as session:
        kb = await session.get(ProjectKnowledgeBase, kb_id)
        return kb.kag_project_id if kb else None


async def ensure_project(kb_id: int) -> int:
    """获取知识库对应的 KAG 项目ID；不存在时创建（namespace=kb_{kb_id}）并回写 kb 表

    返回 kag_project_id；KAG 引擎不可用或创建失败时抛异常（由调用方决定是否终止）。
    """
    async with get_db_session() as session:
        kb = (await session.execute(
            select(ProjectKnowledgeBase).where(ProjectKnowledgeBase.id == kb_id)
        )).scalar_one_or_none()
        if not kb:
            raise ValueError(f'知识库不存在: kb_id={kb_id}')
        if kb.kag_project_id:
            return kb.kag_project_id

    def _resolve() -> int:
        with _kag_lock:
            # knext 的 request 模型构造时会用默认 Configuration() 读 KAG_PROJECT_HOST_ADDR
            # （无此环境变量则从进程CWD向上找 kag_config.yaml，服务进程内不存在会报错）
            os.environ['KAG_PROJECT_HOST_ADDR'] = settings.KAG_OPENSPG_URL
            from knext.project.client import ProjectClient
            client = ProjectClient(host_addr=settings.KAG_OPENSPG_URL)
            namespace = chunk_namespace(kb_id)
            existing = client.get_by_namespace(namespace)
            if existing:
                return int(getattr(existing, 'id', 0) or existing['id'])
            # config 结构照抄本服务端已成功创建项目的模板（产品端生成的完整结构，
            # 缺字段会被服务端解析成空并报"vectorizer cannot be empty"）。
            # vectorizer 沿用服务端已注册的embedding模型（lingshu构图不用它：LLM显式传入、
            # 向量走自有Milvus），地址/模型/Neo4j连接均从配置读取；
            # graph_store.database 按项目名区分；
            # 无 project 键 → KAG运行时 load_config 自动注入 id/namespace/host_addr。
            config = {
                'vectorizer': {
                    'type': 'openai',
                    'provider': 'Ollama',
                    'modelId': settings.KAG_EMBEDDING_MODEL_ID,
                    'model': settings.KAG_EMBEDDING_MODEL,
                    'modelType': 'embedding',
                    'base_url': settings.KAG_EMBEDDING_BASE_URL,
                    'vector_dimensions': str(settings.MILVUS_DIM),
                    'logo': '/img/logo/ollama.png',
                },
                'graph_store': {
                    'uri': settings.KAG_NEO4J_URI,
                    'user': settings.KAG_NEO4J_USER,
                    'password': settings.KAG_NEO4J_PASSWORD,
                    # 服务端按项目name/namespace小写推导Neo4j库名（见重试日志），无须传
                    'database': namespace.lower(),
                },
                'prompt': {'language': 'zh'},
            }
            project = client.create(
                name=namespace, namespace=namespace, config=config,
                desc=f'lingshu知识库{kb_id}',
            )
            return int(project.id)

    project_id = await asyncio.to_thread(_resolve)
    async with get_db_session() as session:
        kb = await session.get(ProjectKnowledgeBase, kb_id)
        kb.kag_project_id = project_id
        session.add(kb)
    log.info('KAG项目已就绪: kb_id=%s project_id=%s', kb_id, project_id)
    return project_id


def build_graph(kag_project_id: int, nodes: list, file_key: str, llm_config: dict) -> int:
    """图谱构建（阻塞，须在线程中执行）：builder链路处理LlamaIndex切分节点

    链路：DictReader（dict→Chunk）→ KnowledgeUnitSchemaFreeExtractor
    （NER→实体标准化→三元组抽取，按项目schema对齐）→ SPGAligner（schema对齐合并）
    → KGWriter（写入Neo4j，label自动加项目namespace前缀）。
    nodes 为 llama-index 切分节点（node_id 与 PG docstore 一致，供删除定位）；
    llm_config 为 {base_url, api_key, model}（OpenAI兼容协议）。
    返回写入的分块数。
    """
    if not nodes:
        return 0
    with _kag_lock:
        _ensure_kag_env(kag_project_id)
        # 懒导入：重依赖且须在 PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION 生效后加载
        from kag.builder.component.aligner.spg_aligner import SPGAligner
        from kag.builder.component.extractor.knowledge_unit_extractor import (
            KnowledgeUnitSchemaFreeExtractor)
        from kag.builder.component.reader.dict_reader import DictReader
        from kag.builder.component.writer.kg_writer import KGWriter
        from kag.common.llm.openai_client import OpenAIClient

        llm = OpenAIClient(
            base_url=llm_config['base_url'], api_key=llm_config['api_key'] or 'EMPTY',
            model=llm_config['model'],
        )
        # 逐个node走链路（本版本 BuilderChainRunner 强依赖scanner+配置化DAG，
        # 直接按组件顺序串行调用等价且更可控）
        reader = DictReader(id_col='id', name_col='name', content_col='content')
        extractor = KnowledgeUnitSchemaFreeExtractor(llm=llm)
        aligner = SPGAligner()
        writer = KGWriter(project_id=kag_project_id)

        written = 0
        for node in nodes:
            chunks = reader.invoke({
                'id': node.node_id, 'name': file_key,
                'content': node.get_content(), 'properties': {'fileKey': file_key},
            }, write_ckpt=False)
            for chunk in chunks:
                for sub_graph in extractor.invoke(chunk, write_ckpt=False):
                    for aligned in aligner.invoke(sub_graph, write_ckpt=False):
                        writer.invoke(aligned, write_ckpt=False)
            written += 1
        log.info('KAG图谱构建完成: project=%s file=%s chunks=%s', kag_project_id, file_key, len(nodes))
        return written


async def delete_file_graph(kag_project_id: int, file_key: str) -> int:
    """删除文件在图中的 Chunk 节点

    chunk 节点ID与PG docstore一致（ref_doc_id=file_key可反查）；实体节点跨文件共享不删。
    返回删除的节点数。
    """
    async with get_db_session() as session:
        node_ids = list((await session.execute(
            select(LlamaDocstoreNode.node_id).where(
                LlamaDocstoreNode.ref_doc_id == file_key)
        )).scalars().all())
    if not node_ids:
        return 0
    return await asyncio.to_thread(
        _delete_file_graph, kag_project_id, file_key, node_ids)


def _delete_file_graph(kag_project_id: int, file_key: str, node_ids: list) -> int:
    """按节点ID删除图中Chunk节点（阻塞，须在线程中执行）"""
    with _kag_lock:
        _ensure_kag_env(kag_project_id)
        from kag.builder.model.sub_graph import SubGraph
        from kag.common.conf import KAG_PROJECT_CONF
        from knext.graph.client import GraphClient

        namespace = KAG_PROJECT_CONF.namespace or chunk_namespace(kag_project_id)
        client = GraphClient(
            host_addr=settings.KAG_OPENSPG_URL, project_id=kag_project_id)
        graph = SubGraph([], [])
        for node_id in node_ids:
            # 删除操作不走KGWriter的namespace补全，须显式带namespace前缀
            graph.add_node(node_id, file_key, f'{namespace}.Chunk', {})
        client.write_graph(graph.to_dict(), 'DELETE', lead_to_builder=False)
        log.info('KAG图数据删除完成: project=%s file=%s nodes=%s',
                 kag_project_id, file_key, len(node_ids))
        return len(node_ids)


async def sync_schema_to_kag(kb_id: int, graph_schema: dict) -> None:
    """确保 KAG 项目存在，并把知识库图谱schema注册到其 SPG schema（保存「图谱schema」时调用）

    流程：ensure_project（REST 创建 project，幂等）→ apply_graph_schema（阻塞，线程中执行）。
    """
    kag_project_id = await ensure_project(kb_id)
    await asyncio.to_thread(apply_graph_schema, kag_project_id, graph_schema)


def apply_graph_schema(kag_project_id: int, graph_schema: dict) -> None:
    """把知识库图谱schema注册到 KAG 项目 SPG schema（阻塞，须在线程中执行）

    graph_schema 为 kb_graph_schemas.schema：
    {"entities":[{"name","desc","properties":{属性名:属性描述}}],
     "relations":[{"name","desc","subjectType","objectType"}]}
    KAG 的 SchemaFreeExtractor 抽取时会把项目 schema 注入 NER/三元组提示词，
    并按 schema 对齐产出（未匹配类型落Others），因此注册后即对抽取生效。
    类型已存在时合并属性/关系（幂等）；关系挂在其起点实体类型的属性上。
    失败仅告警不抛异常（不影响走schema-free模式继续构图）。
    """
    entities = graph_schema.get('entities') or []
    # 归一化：实体名/描述/属性，关系按起点实体分组（subject/object不在实体中的跳过）
    entity_names: list[str] = []
    entity_meta: dict[str, dict] = {}
    for entity in entities:
        name = str(entity.get('name', '')).strip()
        if not name or name in entity_meta:
            continue
        entity_names.append(name)
        entity_meta[name] = {
            'desc': str(entity.get('desc') or '').strip(),
            'properties': {
                str(k).strip(): str(v)
                for k, v in (entity.get('properties') or {}).items()
                if str(k).strip()
            },
        }
    if not entity_names:
        return  # 无实体类型 = schema-free，无需注册
    rels_by_source: dict[str, list] = {}
    for rt in graph_schema.get('relations') or []:
        name = str(rt.get('name', '')).strip()
        subject = str(rt.get('subjectType', '')).strip()
        object_ = str(rt.get('objectType', '')).strip()
        if not (name and subject and object_):
            log.warning('图谱关系类型配置不完整，跳过: %s', rt)
            continue
        if subject not in entity_meta or object_ not in entity_meta:
            log.warning('图谱关系 %s 的subject/object(%s→%s)不在实体类型%s中，跳过',
                        name, subject, object_, entity_names)
            continue
        rels_by_source.setdefault(subject, []).append(
            (name, str(rt.get('desc') or '').strip(), object_))
    with _kag_lock:
        _ensure_kag_env(kag_project_id)
        from knext.schema.client import SchemaClient
        from knext.schema.model.property import Property
        from knext.schema.model.relation import Relation
        from knext.schema.model.spg_type import EntityType

        def _spg_name(name: str, upper: bool = False) -> str | None:
            """转SPG命名规范（类型 ^[A-Z][0-9a-zA-Z]*$；属性/关系 ^[a-z][0-9a-zA-Z]*$，
            不允许下划线/中文）。非法字符按下划线拆分转驼峰；无有效字符返回None。
            已合规的名称原样保留（如 hasPoint）。"""
            raw = str(name).strip()
            pat = r'[A-Z][0-9a-zA-Z]*' if upper else r'[a-z][0-9a-zA-Z]*'
            if re.fullmatch(pat, raw):
                return raw
            parts = [p for p in re.sub(r'[^0-9a-zA-Z]+', '_', raw).split('_') if p]
            if not parts:
                return None
            caps = [p[:1].upper() + p[1:] for p in parts]
            if upper:
                return ''.join(caps)
            return parts[0].lower() + ''.join(caps[1:])

        def _commit_one(session, spg_type, op: str, full_name: str) -> None:
            """逐类型提交，容错服务端schema缓存的短暂不一致：
            刚创建的类型在queryProjectSchema里可能延迟可见，重试时create会报
            "exist same name type"——这类exist错误说明类型实际已写入，视为成功继续，
            下次保存走合并路径收敛。"""
            if op == 'create':
                session.create_type(spg_type)
            else:
                session.update_type(spg_type)
            try:
                session.commit()
            except Exception as e:
                body = str(getattr(e, 'body', '') or e)
                if 'exist' in body:
                    log.warning('KAG schema类型 %s 已存在（服务端缓存延迟可见），跳过: %s',
                                full_name, body)
                    return
                raise

        def _apply() -> tuple[int, int]:
            from kag.common.conf import KAG_PROJECT_CONF
            # SPG规范：类型全名必须带项目namespace前缀（如 Kb3.Device），
            # 否则服务端报 "type name not match project namespace"
            ns = KAG_PROJECT_CONF.namespace or chunk_namespace(kag_project_id)
            prefix = f'{ns}.'
            client = SchemaClient(
                host_addr=settings.KAG_OPENSPG_URL, project_id=str(kag_project_id))
            session = client.create_session()
            existing = session.spg_types  # 服务端已发布类型 {全名: SpgType}
            created = updated = 0
            # 阶段一：建类型+属性（逐类型提交——服务端alter非原子，中途失败会留下
            # 不可见也不可删的脏记录，必须缩小每次提交的事务范围）
            type_full: dict[str, str] = {}  # 原实体名 -> 类型全名
            for etype in entity_names:
                spg_name = _spg_name(etype, upper=True)
                if not spg_name:
                    log.warning('实体类型名 %s 无法转为SPG命名规范，跳过', etype)
                    continue
                full_name = prefix + spg_name
                type_full[etype] = full_name
                meta = entity_meta[etype]
                props = []
                for pname, pdesc in meta['properties'].items():
                    pname2 = _spg_name(pname)
                    if not pname2:
                        log.warning('属性名 %s.%s 无法转为SPG命名规范，跳过', etype, pname)
                        continue
                    props.append(Property(name=pname2, object_type_name=full_name,
                                          name_zh=pname, desc=pdesc or pname))
                if full_name in existing:
                    spg_type = session.get(full_name)
                    missing = [p for p in props if p.name not in spg_type.properties]
                    if not missing:
                        continue
                    for prop in missing:
                        spg_type.add_property(prop)
                    _commit_one(session, spg_type, 'update', full_name)
                    updated += 1
                else:
                    spg_type = EntityType(
                        name=full_name, name_zh=etype,
                        desc=meta['desc'] or f'lingshu知识库定义实体类型{etype}')
                    for prop in props:
                        spg_type.add_property(prop)
                    _commit_one(session, spg_type, 'create', full_name)
                    created += 1
            # 阶段二：挂关系（commit时服务端要求关系客体类型已存在，须在全部类型
            # 就绪后进行；用新会话拿已发布类型的干净对象，避免残留Create操作标记）
            session = client.create_session()
            for etype in entity_names:
                rel_items = rels_by_source.get(etype, [])
                if not rel_items or etype not in type_full:
                    continue
                full_name = type_full[etype]
                try:
                    spg_type = session.get(full_name)
                except (ValueError, KeyError):
                    continue  # 类型延迟可见，下次保存再挂关系
                changed = False
                for rname, rdesc, robj in rel_items:
                    robj_full = type_full.get(robj)
                    rname2 = _spg_name(rname)
                    if not (rname2 and robj_full):
                        log.warning('关系名/客体 %s(%s→%s) 无法转为SPG命名规范，跳过',
                                    rname, etype, robj)
                        continue
                    rel = Relation(name=rname2, object_type_name=robj_full,
                                   name_zh=rname, desc=rdesc or rname)
                    if f'{rel.name}_{rel.object_type_name}' in spg_type.relations:
                        continue  # 键为 {关系名}_{客体类型}，已存在则幂等跳过
                    spg_type.add_relation(rel)
                    changed = True
                if changed:
                    _commit_one(session, spg_type, 'update', full_name)
            return created, updated

        try:
            created, updated = _apply()
            log.info('KAG schema注册完成: project=%s created=%s updated=%s entity_types=%s',
                     kag_project_id, created, updated, entity_names)
        except Exception:
            log.exception('KAG schema注册失败，本次构图按schema-free继续: project=%s',
                          kag_project_id)


async def recall_graph(kb_id: int, question: str, topk: int = 5,
                       filters: list[dict] | None = None) -> list[dict]:
    """KAG知识图谱召回（检索三路之一）：问题全文检索图中Chunk与实体节点

    filters 为规范化过滤条件 [{field, op, value}]，图谱侧仅支持对节点的
    fileKey 属性做后过滤（eq/in 语义，其余操作符忽略）。
    未建图（无KAG项目）返回空列表；召回失败告警返回空（降级不阻断）。
    返回 [{id, content, score, metadata}]，id为 graph:{doc_id} 伪ID（与文本chunk区分）。
    """
    kag_project_id = await get_project(kb_id)
    if not kag_project_id:
        return []
    return await asyncio.to_thread(_recall_graph, kag_project_id, question, topk, filters)


def _recall_graph(kag_project_id: int, question: str, topk: int,
                  filters: list[dict] | None) -> list[dict]:
    """图谱召回（阻塞，须在线程中执行）：SPGServer全文检索接口"""
    file_filters = set()
    for f in (filters or []):
        if f.get('field') == 'file_key' and f.get('op') in ('eq', 'in'):
            values = f.get('value')
            file_filters = set(values if isinstance(values, list) else [values])
    with _kag_lock:
        _ensure_kag_env(kag_project_id)
        from knext.search.client import SearchClient
        client = SearchClient(
            host_addr=settings.KAG_OPENSPG_URL, project_id=kag_project_id)
        try:
            records = client.search_text(question, topk=topk) or []
        except Exception:
            log.exception('KAG图谱召回失败: project=%s', kag_project_id)
            return []
        items = []
        for rec in records:
            fields = getattr(rec, 'fields', None) or {}
            file_key = str(fields.get('fileKey') or fields.get('file_key') or '')
            if file_filters and file_key and file_key not in file_filters:
                continue
            # Chunk节点直接用content；实体节点用name及关键属性拼上下文
            content = str(fields.get('content') or '').strip()
            if not content:
                props = {k: v for k, v in fields.items()
                         if k not in ('id', 'name', 'label', 'fileKey', 'file_key')}
                name = str(fields.get('name') or '').strip()
                label = str(fields.get('label') or '').strip()
                content = f'{label} {name} {props}'.strip() if name else ''
            if not content:
                continue
            items.append({
                'id': f"graph:{getattr(rec, 'doc_id', None) or fields.get('id') or fields.get('name')}",
                'content': content,
                'score': float(getattr(rec, 'score', 0) or 0),
                'metadata': {
                    'label': str(fields.get('label') or ''),
                    'name': str(fields.get('name') or ''),
                    'fileKey': file_key or None,
                },
            })
        return items


async def drop_project(kb_id: int, kag_project_id: int | None) -> None:
    """知识库级联删除时清理对应 KAG 项目

    OpenSPG REST 未提供项目删除端点（ProjectClient无delete方法），仅记录告警提示
    手动在KAG产品端清理；namespace按 kb_{kb_id} 唯一命名，残留数据不会跨库污染。
    """
    if not kag_project_id:
        return
    log.warning(
        'KAG项目无法通过API删除（OpenSPG未提供删除端点），请在KAG产品端手动清理: '
        'kb_id=%s namespace=%s project_id=%s 引擎=%s',
        kb_id, chunk_namespace(kb_id), kag_project_id, settings.KAG_OPENSPG_URL)
