"""检索服务：三路并行召回（ES全文/Milvus向量/KAG图谱）→ RRF融合 → reranker精排 → 过滤分页

- 三路召回前先做元数据过滤前置：过滤条件转换为各路自身的过滤表达
  （ES: term/terms子句；Milvus: expr；KAG: fileKey属性后过滤）
- RRF融合：score = Σ 1/(k + rank)，k=60；同chunk（node_id）跨路去重合并来源
- reranker：注册表rerank类型模型（OpenAI兼容 /rerank 协议）；
  未配置或调用失败时降级为RRF融合分排序
- similarity_threshold 语义为 rerank 相关性分（未rerank时不做阈值过滤）
"""

import asyncio
import logging

from modules.document import es_store, kag_store, milvus_store
from modules.provider import model_factory
from modules.retriever.schema import RetrievalRequest

log = logging.getLogger(__name__)

# RRF常数（标准取值60，越大排名差异越平缓）
RRF_K = 60


def _normalize_filters(meta_filter: dict) -> list[dict]:
    """请求过滤条件 → 规范化列表 [{field, op, value}]（三路共用）

    值支持三种写法：标量=eq；列表=in；{"op": "eq|in|gt|gte|lt|lte|contains", "value": ...}
    """
    filters = []
    for field, value in (meta_filter or {}).items():
        if isinstance(value, dict) and 'op' in value:
            filters.append({'field': field, 'op': str(value['op']).lower(),
                            'value': value.get('value')})
        elif isinstance(value, (list, tuple, set)):
            filters.append({'field': field, 'op': 'in', 'value': list(value)})
        else:
            filters.append({'field': field, 'op': 'eq', 'value': value})
    return filters


def _as_candidate(hit: dict, source: str) -> dict:
    """各路召回结果 → 统一候选结构"""
    return {
        'id': str(hit.get('node_id') or hit.get('id') or ''),
        'content': hit.get('content') or '',
        'file_key': hit.get('file_key'),
        'metadata': hit.get('metadata') or {},
        'sources': [source],
        'score': float(hit.get('score') or 0),
    }


async def _recall_es(kb_ids: list[str], question: str,
                     filters: list[dict], top_k: int) -> list[dict]:
    """ES BM25全文召回（同步SDK，线程中执行）"""
    all_hits = []
    for kb_id in kb_ids:
        try:
            hits = await asyncio.to_thread(
                es_store.search, f'kb_{kb_id}', question, filters, top_k)
            all_hits.extend(hits)
        except Exception:
            log.exception('ES召回失败: kb=%s', kb_id)
    return all_hits


async def _recall_vector(kb_ids: list[str], question: str,
                         filters: list[dict], top_k: int) -> list[dict]:
    """Milvus向量召回：问题向量化（与入库同源embedding配置）后按库检索"""
    try:
        embedding = await model_factory.resolve_embedding(None)
        query_vector = await embedding.aget_query_embedding(question)
    except Exception:
        log.exception('查询向量化失败（embedding未登记或调用异常），向量召回降级跳过')
        return []
    all_hits = []
    for kb_id in kb_ids:
        try:
            hits = await asyncio.to_thread(
                milvus_store.search, f'kb_{kb_id}', query_vector, filters, top_k)
            all_hits.extend(hits)
        except Exception:
            log.exception('向量召回失败: kb=%s', kb_id)
    return all_hits


async def _recall_graph(kb_ids: list[str], question: str,
                        filters: list[dict], top_k: int) -> list[dict]:
    """KAG图谱召回（kag_store内部持锁+线程执行；未建图返回空，不阻断）"""
    tasks = []
    for kb_id in kb_ids:
        if not str(kb_id).isdigit():
            log.warning('图谱召回跳过：知识库ID非法: %s', kb_id)
            continue
        tasks.append(kag_store.recall_graph(int(kb_id), question, top_k, filters))
    all_hits = []
    for part in await asyncio.gather(*tasks, return_exceptions=True):
        if isinstance(part, Exception):
            log.warning('图谱召回异常（降级跳过）: %s', part)
        else:
            all_hits.extend(part)
    return all_hits


def _fuse_rrf(hits_by_source: list[tuple[str, list[dict]]], top_k: int) -> list[dict]:
    """RRF融合：score = Σ 1/(k + rank)，同id去重并合并来源；返回按融合分降序的候选"""
    fused: dict[str, dict] = {}
    for source, hits in hits_by_source:
        for rank, hit in enumerate(hits):
            cand = _as_candidate(hit, source)
            if not cand['id'] or not cand['content']:
                continue
            item = fused.setdefault(cand['id'], cand)
            if source not in item['sources']:
                item['sources'].append(source)
            item['rrf_score'] = item.get('rrf_score', 0.0) + 1.0 / (RRF_K + rank + 1)
    ranked = sorted(fused.values(), key=lambda x: x['rrf_score'], reverse=True)
    return ranked[:top_k]


async def _rerank(question: str, candidates: list[dict]) -> list[dict] | None:
    """reranker精排：返回按相关性分降序的候选；未配置/失败返回None（调用方降级）"""
    config = await model_factory.resolve_rerank_config(None)
    if not config:
        log.info('注册表未配置rerank模型，降级为RRF融合分排序')
        return None
    model, base_url, api_key = config
    docs = [c['content'][:1500] for c in candidates]
    try:
        ranked = await model_factory.invoke_rerank(
            model, base_url, api_key, question, docs)
    except Exception:
        log.exception('rerank调用失败（降级为RRF融合分排序）: model=%s', model)
        return None
    out = []
    for index, score in ranked:
        if 0 <= index < len(candidates):
            item = dict(candidates[index])
            item['score'] = score
            out.append(item)
    return out


async def retrieval(request: RetrievalRequest) -> dict:
    """检索主流程：三路并行召回 → RRF融合 → rerank → 阈值过滤 → 分页"""
    kb_ids = [str(d).strip() for d in request.dataset_ids if str(d).strip()]
    filters = _normalize_filters(request.meta_data_filter)
    # 每路召回量：与重排候选数对齐（RRF融合后仍能喂满reranker）
    top_recall = max(request.rerank_candidates_count, request.page_size)

    tasks = [
        _recall_es(kb_ids, request.question, filters, top_recall),
        _recall_vector(kb_ids, request.question, filters, top_recall),
        _recall_graph(kb_ids, request.question, filters, request.graph_recall_topk)
        if request.enable_graph_recall else _empty(),
    ]
    es_hits, vec_hits, graph_hits = await asyncio.gather(*tasks)

    candidates = _fuse_rrf(
        [('es', es_hits), ('vector', vec_hits), ('graph', graph_hits)],
        top_k=max(request.rerank_candidates_count, request.page_size))

    reranked = await _rerank(request.question, candidates)
    if reranked is not None:
        candidates = reranked
        # rerank相关性分（0~1）与threshold同尺度，此时才做阈值过滤
        candidates = [c for c in candidates
                      if c['score'] >= request.similarity_threshold]
    else:
        for c in candidates:  # 降级：直接用RRF融合分
            c['score'] = c.pop('rrf_score', 0.0)

    total = len(candidates)
    start = (request.page - 1) * request.page_size
    page_items = candidates[start:start + request.page_size]
    chunks = [
        {
            'id': c['id'],
            'content': c['content'],
            'file_key': c['file_key'],
            'score': round(c['score'], 6),
            'recall_source': c['sources'],
            'metadata': c['metadata'],
        }
        for c in page_items
    ]
    log.info('检索完成: question=%s kb=%s total=%s(三路: es=%s vector=%s graph=%s)',
             request.question, kb_ids, total, len(es_hits), len(vec_hits), len(graph_hits))
    return {
        'total': total,
        'page': request.page,
        'page_size': request.page_size,
        'chunks': chunks,
    }


async def _empty() -> list[dict]:
    return []
