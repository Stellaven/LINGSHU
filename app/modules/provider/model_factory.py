"""模型注册表 → llama_index 模型实例解析

文件处理策略中的 embedModel/llmModel 为 models 表中的模型名，按名称查找其
所属实例（model_instances：base_url/api_key）构建 llama_index 模型实例。
统一按 OpenAI 兼容协议调用（Anthropic/Gemini 原生协议暂不支持）。
"""

import logging

from sqlalchemy import and_, func, select

from core.dependencies import get_db_session
from config.settings import settings
from db.pg.orm_models import Model, ModelInstance

log = logging.getLogger(__name__)


async def _lookup_instance(model_name: str, model_type: str) -> tuple[str, str] | None:
    """按模型名查实例连接配置：优先已标注类型的同名模型，其次未标注类型的"""
    async with get_db_session() as session:
        for cond in (
            and_(Model.name == model_name, func.lower(Model.model_type) == model_type),
            and_(Model.name == model_name, Model.model_type.is_(None)),
        ):
            row = (await session.execute(
                select(ModelInstance.base_url, ModelInstance.api_key)
                .join(Model, Model.instance_id == ModelInstance.id)
                .where(cond)
                .order_by(Model.id)
            )).first()
            if row:
                return row[0], row[1]
    return None


class ModelNotRegisteredError(Exception):
    """模型未在注册表登记（无同名模型或实例连接配置缺失）"""


async def resolve_embedding(model_name: str | None):
    """策略embedModel → embedding实例；未指定或注册表未登记时报错"""
    name = (model_name or 'bge-m3').strip() or 'bge-m3'
    row = await _lookup_instance(name, 'embedding')
    if not row:
        raise ModelNotRegisteredError(
            f'嵌入模型 {name} 未在模型注册表登记（需为项目内实例下的 embedding 类型模型）')
    from llama_index.embeddings.openai import OpenAIEmbedding
    base_url, api_key = row
    # Ollama等本地网关不校验Key，空Key用占位符满足SDK必填校验
    return OpenAIEmbedding(model=name, api_key=api_key or 'EMPTY', api_base=base_url or None)


async def resolve_llm(model_name: str | None):
    """策略llmModel → LLM实例；未配置或注册表未登记时返回None（数据提取跳过）"""
    name = (model_name or '').strip()
    if not name:
        return None
    row = await resolve_llm_config(name)
    if not row:
        return None
    base_url, api_key = row
    from llama_index.llms.openai import OpenAI
    return OpenAI(model=name, api_key=api_key or 'EMPTY', api_base=base_url or None)


async def resolve_llm_config(model_name: str | None) -> tuple[str, str] | None:
    """模型名 → (base_url, api_key) 连接配置（供KAG等需自建OpenAI client的场景）"""
    name = (model_name or '').strip()
    if not name:
        return None
    row = await _lookup_instance(name, 'chat')
    if not row:
        log.warning('LLM %s 未在模型注册表登记（chat类型）', name)
        return None
    return row


async def resolve_rerank_config(model_name: str | None) -> tuple[str, str, str] | None:
    """rerank模型名 → (model, base_url, api_key) 连接配置

    未指定名称时取注册表中第一个 rerank 类型模型；注册表无 rerank 模型返回 None
    （检索侧降级为 RRF 融合分排序）。
    """
    async with get_db_session() as session:
        if model_name:
            cond = and_(Model.name == model_name.strip(),
                        func.lower(Model.model_type) == 'rerank')
        else:
            cond = func.lower(Model.model_type) == 'rerank'
        row = (await session.execute(
            select(Model.name, ModelInstance.base_url, ModelInstance.api_key)
            .join(ModelInstance, Model.instance_id == ModelInstance.id)
            .where(cond)
            .order_by(Model.id)
        )).first()
    if not row:
        return None
    return row[0], row[1], row[2] or 'EMPTY'


async def invoke_rerank(model: str, base_url: str, api_key: str, query: str,
                        documents: list[str], top_n: int | None = None) -> list[tuple[int, float]]:
    """调用 rerank 模型（OpenAI兼容 /rerank 协议，SiliconFlow/Jina风格）

    返回 [(候选下标, 相关性分数)]，按分数降序。失败抛 httpx 异常由调用方降级处理。
    """
    url = base_url.strip().rstrip('/') + '/rerank'
    payload: dict = {'model': model, 'query': query, 'documents': documents}
    if top_n:
        payload['top_n'] = top_n
    headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
    import httpx
    async with httpx.AsyncClient(timeout=settings.MODEL_REQUEST_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        results = resp.json().get('results') or []
    return [(r['index'], float(r.get('relevance_score') or 0)) for r in results
            if isinstance(r, dict) and 'index' in r]
