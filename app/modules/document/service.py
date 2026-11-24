import asyncio
import logging
import os.path
import re

from llama_index.core import SimpleDirectoryReader
from llama_index.core.async_utils import run_jobs
from llama_index.core.bridge.pydantic import Field, SerializeAsAny
from llama_index.core.extractors import (
    KeywordExtractor, QuestionsAnsweredExtractor, SummaryExtractor, TitleExtractor,
)
from llama_index.core.extractors.interface import BaseExtractor
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.llms.llm import LLM
from llama_index.core.node_parser import SemanticSplitterNodeParser, SentenceSplitter, \
    SentenceWindowNodeParser, HierarchicalNodeParser, HTMLNodeParser, JSONNodeParser, \
    MarkdownNodeParser, CodeSplitter, TokenTextSplitter, SimpleFileNodeParser
from llama_index.core.prompts import PromptTemplate
from llama_index.core.schema import BaseNode, MetadataMode

from modules.document import docling_service, es_store, milvus_store
from modules.document.repository import PostgresDocumentStore
from modules.provider import model_factory

log = logging.getLogger(__name__)

ENTITY_EXTRACT_TEMPLATE = """\
从下面的文本中抽取命名实体（人名、组织机构、地点、时间、产品、技术术语等专有名词），\
以顿号分隔输出，最多 {max_entities} 个，不要输出任何其他内容。

文本：
{content}

实体："""


class EntityExtractor(BaseExtractor):
    """基于LLM的实体抽取：识别块中的命名实体并写入元数据 extracted_entities"""

    llm: SerializeAsAny[LLM] = Field(description='用于抽取实体的LLM。')
    max_entities: int = Field(default=20, gt=0, description='单块最多抽取的实体数。')

    def __init__(self, llm: LLM = None, **kwargs) -> None:
        from llama_index.core.settings import Settings
        super().__init__(llm=llm or Settings.llm, **kwargs)

    @classmethod
    def class_name(cls) -> str:
        return 'EntityExtractor'

    async def aextract(self, nodes: list[BaseNode]) -> list[dict]:
        jobs = [
            self.llm.apredict(
                PromptTemplate(template=ENTITY_EXTRACT_TEMPLATE),
                max_entities=self.max_entities,
                content=node.get_content(MetadataMode.LLM),
            )
            for node in nodes
        ]
        results = await run_jobs(
            jobs=jobs, show_progress=self.show_progress, num_workers=self.num_workers)
        return [{'extracted_entities': result} for result in results]


async def process_file(file_path: str, collection_name: str = None,
                       strategy: dict = None, overwrite: bool = True,
                       file_key: str = None, kb_id: int = None) -> int:
    """处理已落盘文件：解析→前置提取→切分→后置提取→向量化入库（IngestionPipeline，任务worker共用入口）

    strategy 为 file_parse_strategies 序列化结果：
    - stages 为编排序列（parser/pre_extract/split/post_extract），缺失时由单值字段派生（历史数据）
    - parser=Docling 时走本地docling-serve服务解析（输出Markdown），否则用内置SimpleDirectoryReader
    - embedModel 为模型注册表中的模型名（未登记时报错终止）
    - pre_extract 在分块前按文档级执行，post_extract 在分块后按节点级执行，
      每个提取器实例独立指定LLM（未配置该LLM时该提取器跳过）
    - split 为分块器序列，按顺序级联：后一级作用于前一级产出的每个节点
    - graph=True 时追加 KAG 图谱构建（节点→三元组→Neo4j），抽取LLM取编排条目中
      第一个已配置的模型；kb_id 用于定位/懒创建对应的 KAG 项目
    返回分块数量。

    file_key：文件级确定性标识（如 "file:{file_id}"）。任务重试/崩溃恢复会重复执行
    同一文件，指定 file_key 时以它为源文档ID，入库前先清除旧分块（PG docstore
    按 ref_doc_id 删、Milvus/ES 按 file_key 删），保证重复执行结果幂等。
    """
    strategy = strategy or {}
    suffix = os.path.splitext(file_path)[1]
    stages = _strategy_stages(strategy)

    # 策略parser=Docling时走docling-serve解析（输出Markdown），否则内置reader
    parser = (stages.get('parser') or [None])[0]
    if parser == 'Docling':
        docs = await docling_service.parse_file(file_path)
    else:
        reader = SimpleDirectoryReader(file_path)
        # load_data含文件IO和文档解析，放到线程执行，避免阻塞事件循环
        docs = await asyncio.to_thread(reader.load_data)

    # 模型按名称查注册表：嵌入模型未登记时报错
    embed_model = await model_factory.resolve_embedding(strategy.get('embedModel'))

    # 文档存储与向量存储
    doc_store = PostgresDocumentStore()
    vector_store = milvus_store.vector_store(collection_name, overwrite=overwrite)

    if file_key:
        # 源文档ID改为确定性值（默认随临时文件路径元数据生成，每次运行都不同），
        # 使重试/恢复重跑时能按 ref_doc_id 定位并清除上一轮的旧分块
        for i, doc in enumerate(docs):
            doc.id_ = file_key if len(docs) == 1 else f'{file_key}:{i}'
        for key in {doc.id_ for doc in docs}:
            await asyncio.to_thread(doc_store.delete_ref_doc, key, False)
            await asyncio.to_thread(milvus_store.delete_chunks, collection_name, key)
            await asyncio.to_thread(es_store.delete_chunks, collection_name, key)

    # 编排序列即 transformations 顺序：前置提取（文档级）→ 级联分块 → 后置提取（节点级），
    # embedding 由 pipeline 统一追加在末尾；docstore不挂pipeline（其upsert只存源文档不存
    # 切分节点），切分节点在run后自行落库，保证hierarchical等父子检索可从docstore取回节点
    split_parsers = (
        [_build_node_parser(chunker, suffix, embed_model)
         for chunker in stages.get('split')]
        if stages.get('split') else [_fallback_node_parser(suffix.lstrip('.').casefold())]
    )
    transformations = [
        *await _build_stage_extractors(stages.get('pre_extract') or [], '文档级'),
        *split_parsers,
        *await _build_stage_extractors(stages.get('post_extract') or [], '块级'),
        # llama-index 0.10+ 移除了 IngestionPipeline 的 embed_model 参数：
        # 嵌入模型须显式作为最后一个 transformation（acall 就地写入向量），
        # 否则节点无向量，pipeline 只会写入已有 embedding 的节点（向量库为空）
        embed_model,
    ]
    pipeline = IngestionPipeline(
        transformations=transformations,
        vector_store=vector_store,
    )
    # 提取（LLM调用）、切分、embedding、Milvus写入全程同步且耗时，放到线程执行
    nodes = await asyncio.to_thread(pipeline.run, documents=docs, show_progress=True)
    # 切分节点落PG docstore（ref_doc_id=file_key，供删除清理与父子检索定位）
    await asyncio.to_thread(doc_store.add_documents, nodes)
    # 分块写入ES全文索引（内容原文+元数据，doc id=node_id）
    count = await asyncio.to_thread(es_store.index_nodes, collection_name, nodes)
    # KAG图谱构建（graph开关在策略上；项目与Milvus collection/ES索引一一对应）
    if strategy.get('graph') and kb_id:
        await _build_knowledge_graph(kb_id, nodes, file_key, stages)
    return count


async def _build_knowledge_graph(kb_id: int, nodes: list, file_key: str, stages: dict) -> None:
    """KAG图谱构建：懒创建项目 → 注册知识库图谱schema → 分块节点抽取三元组写入Neo4j

    图谱schema为知识库维度（「图谱schema」页签维护，graph=True的策略要求已创建）；
    抽取LLM取编排（pre/post_extract）条目中第一个已配置的模型；未配置时跳过并告警。
    图谱失败不阻断文件入库主流程（仅记日志）。
    """
    llm_name = next(
        (entry.get('llm') for entry in
         (stages.get('pre_extract') or []) + (stages.get('post_extract') or [])
         if entry.get('llm')), None)
    llm_config = await model_factory.resolve_llm_config(llm_name) if llm_name else None
    if not llm_config:
        log.warning('图谱抽取未配置可用LLM，跳过KAG构图: kb_id=%s file=%s', kb_id, file_key)
        return
    try:
        from modules.document import graph_schema_repository, kag_store
        # 知识库图谱schema：确保KAG项目存在并注册到SPG schema（抽取提示词自动携带并对齐产出）
        graph_schema = await graph_schema_repository.get_schema(kb_id)
        if graph_schema:
            await kag_store.sync_schema_to_kag(kb_id, graph_schema)
        kag_project_id = await kag_store.ensure_project(kb_id)
        await asyncio.to_thread(
            kag_store.build_graph, kag_project_id, nodes, file_key,
            {'base_url': llm_config[0], 'api_key': llm_config[1], 'model': llm_name})
    except Exception:
        log.exception('KAG图谱构建失败（不影响向量/全文入库）: kb_id=%s file=%s', kb_id, file_key)


def _strategy_stages(strategy: dict) -> dict:
    """策略编排序列（保存时已校验至少含解析器与分块器）"""
    return strategy.get('stages') or {}


async def _build_stage_extractors(entries: list, scope: str) -> list:
    """按编排条目构建提取器集合，每个实例独立解析LLM与参数；未配置LLM的条目跳过"""
    out = []
    for entry in entries:
        extractor_id = entry.get('id')
        llm = await model_factory.resolve_llm(entry.get('llm'))
        if llm is None:
            log.warning('%s提取器 %s 未配置LLM，跳过该提取器', scope, extractor_id)
            continue
        out.extend(_build_extractor_set(extractor_id, llm, entry.get('params') or {}))
    return out


def _build_extractor_set(extractor: str, llm, params: dict | None = None) -> list:
    """单个提取器ID → 元数据提取器集合（params为参数配置，未提供的键取默认值）"""
    params = params or {}
    if extractor == 'title':
        # 推断文档标题并写入 document_title 元数据
        # nodes：参与标题推断的前置节点数（长文档可增大取样提升准确度）
        return [TitleExtractor(llm=llm, nodes=_param_int(params, 'nodes', 5, lo=1, hi=50))]
    if extractor == 'summary':
        # 概括块内容生成摘要，写入 section_summary 元数据（summaries 固定 ['self']）
        return [SummaryExtractor(llm=llm)]
    if extractor == 'question':
        # 生成每个块可回答的问题，写入 questions_this_excerpt_can_answer
        return [QuestionsAnsweredExtractor(
            llm=llm, questions=_param_int(params, 'questions', 5, lo=1, hi=20))]
    if extractor == 'keyword':
        # 提取块关键词，写入 excerpt_keywords 元数据
        return [KeywordExtractor(llm=llm, keywords=_param_int(params, 'keywords', 5, lo=1, hi=20))]
    if extractor == 'entity':
        # 抽取命名实体，写入 extracted_entities
        return [EntityExtractor(llm=llm, max_entities=_param_int(params, 'max_entities', 20, lo=1, hi=100))]
    return []


def build_file_key(file_id=None, object_name: str = '') -> str:
    """文件级确定性标识：重试/恢复重跑的幂等清理与文件删除共用同一key定位分块

    payload中的fileId为kb_files记录ID（字符串形式）；无记录时回退对象key。
    """
    return f"file:{file_id if file_id else object_name}"


async def delete_file_chunks(collection_name: str, file_key: str, kb_id: int = None) -> None:
    """删除文件的全部分块：KAG图按chunk节点删（须在docstore删除前反查节点ID）、PG docstore按ref_doc_id删、Milvus/ES按file_key删"""
    if kb_id:
        await _delete_kag_file(kb_id, file_key)
    await asyncio.to_thread(PostgresDocumentStore().delete_ref_doc, file_key, False)
    await asyncio.to_thread(milvus_store.delete_chunks, collection_name, file_key)
    await asyncio.to_thread(es_store.delete_chunks, collection_name, file_key)


async def _delete_kag_file(kb_id: int, file_key: str) -> None:
    """删除文件在KAG图中的Chunk节点（未建图时静默跳过；失败仅告警，不阻断删除主流程）"""
    try:
        from modules.document import kag_store
        kag_project_id = await kag_store.get_project(kb_id)
        if kag_project_id:
            await kag_store.delete_file_graph(kag_project_id, file_key)
    except Exception:
        log.warning('KAG图数据删除失败: kb_id=%s file=%s', kb_id, file_key, exc_info=True)


async def delete_file_docstore_chunks(file_key: str) -> None:
    """仅删除PG docstore分块（整库删除时向量/全文由collection与索引级drop清理）"""
    await asyncio.to_thread(PostgresDocumentStore().delete_ref_doc, file_key, False)


async def drop_kb_collection(kb_id: int) -> None:
    """删除知识库的Milvus collection与ES索引，并级联清理KAG项目（不存在时静默跳过）"""
    collection_name = f"kb_{kb_id}"
    await asyncio.to_thread(milvus_store.drop_collection, collection_name)
    await asyncio.to_thread(es_store.drop_index, collection_name)
    from modules.document import kag_store
    kag_project_id = await kag_store.get_project(kb_id)
    await kag_store.drop_project(kb_id, kag_project_id)


def _split_entry(chunker: str | dict) -> tuple[str | None, dict]:
    """分块器编排条目 → (id, params)；兼容历史纯字符串 id（等价于默认参数）"""
    if isinstance(chunker, str):
        return chunker, {}
    return chunker.get('id'), dict(chunker.get('params') or {})


def _param_int(params: dict, key: str, default: int,
               lo: int | None = None, hi: int | None = None) -> int:
    """读取整型参数：缺失用默认值，非法/越界取值回退默认并告警"""
    if params.get(key) in (None, ''):
        return default
    try:
        value = int(params[key])
    except (TypeError, ValueError):
        log.warning('分块参数 %s=%r 不是整数，回退默认 %s', key, params[key], default)
        return default
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        log.warning('分块参数 %s=%d 超出允许范围，回退默认 %s', key, value, default)
        return default
    return value


def _param_str(params: dict, key: str, default: str) -> str:
    """读取字符串参数：缺失/空串用默认值"""
    value = params.get(key)
    if value is None or str(value).strip() == '':
        return default
    return str(value)


def _param_tags(params: dict, key: str, default: list[str]) -> list[str]:
    """读取标签列表参数：支持逗号分隔字符串或字符串数组"""
    raw = params.get(key)
    if raw in (None, ''):
        return default
    items = raw.split(',') if isinstance(raw, str) else raw
    tags = [str(item).strip() for item in items if str(item).strip()]
    return tags or default


def _param_chunk_sizes(params: dict, key: str, default: list[int]) -> list[int]:
    """读取层级块长参数：支持逗号分隔字符串或数组；须为逐级递减的正整数"""
    raw = params.get(key)
    if raw in (None, ''):
        return default
    items = raw.split(',') if isinstance(raw, str) else raw
    try:
        sizes = [int(item) for item in items]
    except (TypeError, ValueError):
        log.warning('分块参数 %s=%r 含非整数层级，回退默认 %s', key, raw, default)
        return default
    if (len(sizes) < 2 or any(size <= 0 for size in sizes)
            or any(sizes[i] <= sizes[i + 1] for i in range(len(sizes) - 1))):
        log.warning('分块参数 %s=%s 不是逐级递减的正整数层级，回退默认 %s',
                    key, sizes, default)
        return default
    return sizes


# HTMLNodeParser 默认提取标签（与 llama_index DEFAULT_TAGS 一致）
HTML_DEFAULT_TAGS = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'b', 'i', 'u', 'section']
# SentenceSplitter 默认句内回退切分正则（与 llama_index CHUNKING_REGEX 一致）
SENTENCE_CHUNKING_REGEX = r'[^,.;。？！]+[,.;。？！]?|[,.;。？！]'


def _unescape_separator(value: str) -> str:
    """分隔符输入的转义还原：\n → 换行、\t → 制表符（前端文本框不便输入真实换行）"""
    return value.replace('\\n', '\n').replace('\\t', '\t')


def _param_regex(params: dict, key: str, default: str) -> str:
    """读取正则参数：缺失/空串用默认值，编译失败回退默认并告警"""
    raw = params.get(key)
    if raw is None or str(raw).strip() == '':
        return default
    value = str(raw)
    try:
        re.compile(value)
    except re.error as exc:
        log.warning('分块参数 %s=%r 不是合法正则（%s），回退默认', key, raw, exc)
        return default
    return value


def _build_node_parser(chunker: str | dict | None, suffix: str, embed_model):
    """按策略chunker条目构建分块器（params为参数配置，未提供的键取默认值）；

    未指定/未知取值时按文件后缀回退（与历史行为一致）
    """
    chunker_id, params = _split_entry(chunker) if chunker is not None else (None, {})
    ext = (suffix or '').lstrip('.').casefold()
    if chunker_id == 'semantic':
        # 嵌入模型继承自策略（process_file 解析 strategy.embedModel 后传入），
        # 语义相似度计算与其余分块器共享同一嵌入维度，不支持经 params 覆盖
        return SemanticSplitterNodeParser(
            buffer_size=_param_int(params, 'buffer_size', 1, lo=1),
            breakpoint_percentile_threshold=_param_int(
                params, 'breakpoint_percentile_threshold', 95, lo=1, hi=100),
            embed_model=embed_model)
    if chunker_id == 'sentence':
        chunk_size = _param_int(params, 'chunk_size', 200, lo=1)
        # 重叠须小于块大小（llama-index 初始化会校验 overlap > size 直接报错）
        chunk_overlap = min(_param_int(params, 'chunk_overlap', 50, lo=0), chunk_size - 1)
        return SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            paragraph_separator=_unescape_separator(
                _param_str(params, 'paragraph_separator', '\n\n\n')),
            secondary_chunking_regex=_param_regex(
                params, 'secondary_chunking_regex', SENTENCE_CHUNKING_REGEX),
        )
    if chunker_id == 'token':
        # 按固定 token 数切分（llama_index 默认 tokenizer），块大小精确可控
        chunk_size = _param_int(params, 'chunk_size', 512, lo=1)
        chunk_overlap = min(_param_int(params, 'chunk_overlap', 50, lo=0), chunk_size - 1)
        return TokenTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if chunker_id == 'sentence_window':
        return SentenceWindowNodeParser.from_defaults(
            window_size=_param_int(params, 'window_size', 3, lo=1))
    if chunker_id == 'hierarchical':
        return HierarchicalNodeParser.from_defaults(
            chunk_sizes=_param_chunk_sizes(params, 'chunk_sizes', [1024, 512, 256]),
            chunk_overlap=_param_int(params, 'chunk_overlap', 20, lo=0))
    if chunker_id == 'markdown':
        return MarkdownNodeParser(
            header_path_separator=_param_str(params, 'header_path_separator', '/'))
    if chunker_id == 'html':
        return HTMLNodeParser(tags=_param_tags(params, 'tags', HTML_DEFAULT_TAGS))
    if chunker_id == 'json':
        return JSONNodeParser()
    if chunker_id == 'code':
        code_lang = get_lang_by_suffix(ext)
        if code_lang:
            count_mode = _param_str(params, 'count_mode', 'char')
            if count_mode not in ('char', 'token'):
                log.warning('分块参数 count_mode=%r 仅支持 char/token，回退默认 char', count_mode)
                count_mode = 'char'
            chunk_lines = _param_int(params, 'chunk_lines', 40, lo=1)
            return CodeSplitter(
                code_lang,
                chunk_lines=chunk_lines,
                chunk_lines_overlap=min(
                    _param_int(params, 'chunk_lines_overlap', 15, lo=0), chunk_lines - 1),
                max_chars=_param_int(params, 'max_chars', 1500, lo=1),
                count_mode=count_mode,
                max_tokens=_param_int(params, 'max_tokens', 512, lo=1))
        log.warning('代码分块缺少语言映射（%s），回退句子分割器', ext)
        return SentenceSplitter(chunk_size=200, chunk_overlap=50)
    if chunker_id == 'simple_file':
        # 按文件后缀自动选择结构化分块（md/html/json），其他类型整文成块
        return SimpleFileNodeParser.from_defaults()
    if chunker_id:
        log.warning('未知分块器 %s，按文件后缀回退选择', chunker_id)
    return _fallback_node_parser(ext)


def _fallback_node_parser(ext: str):
    """未指定/未知chunker时按后缀回退：html/json/md结构化解析、代码文件语法切分，
    默认句子分割器"""
    by_ext = {'html': HTMLNodeParser, 'htm': HTMLNodeParser,
              'json': JSONNodeParser, 'md': MarkdownNodeParser}
    if ext in by_ext:
        return by_ext[ext]()
    code_lang = get_lang_by_suffix(ext)
    if code_lang:
        return CodeSplitter(code_lang)
    return SentenceSplitter(chunk_size=200, chunk_overlap=50)


def get_lang_by_suffix(suffix: str) -> str | None:
    # 后缀 -> 编程语言映射，key不要带点
    ext_map = {
        "py": "Python",
        "java": "Java",
        "js": "JavaScript",
        "ts": "TypeScript",
        "go": "Go",
        "c": "C",
        "cpp": "C++",
        "h": "C/C++ Header",
        "hpp": "C++ Header",
        "cs": "C#",
        "php": "PHP",
        "rb": "Ruby",
        "rs": "Rust",
        "scala": "Scala",
        "kt": "Kotlin",
        "kts": "Kotlin Script",
        "swift": "Swift",
        "dart": "Dart",
        "vue": "Vue",
        "html": "HTML",
        "htm": "HTML",
        "css": "CSS",
        "sql": "SQL",
        "sh": "Shell",
        "bash": "Bash",
        "zsh": "Zsh",
        "bat": "Batch",
        "cmd": "Batch",
        "yaml": "YAML"
    }

    if not suffix:
        return None
    s = suffix.strip()
    # 去掉开头的点
    if s.startswith("."):
        s = s[1:]
    s = s.casefold()
    return ext_map.get(s)
