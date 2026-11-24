"""Elasticsearch 分块全文索引封装

service.py 只调用本模块暴露的函数，不直接操作 ES SDK：
- index_nodes：文件分块批量写入（索引不存在时自动创建）
- delete_chunks：按 file_key 删除单文件全部分块
- drop_index：删除整个索引（整库清理用）

索引命名与Milvus collection一致（kb_{kb_id}），每个知识库一个索引；
doc id = 分块node_id，重复写入自动覆盖（配合file_key幂等清理）。
"""

import logging

from elasticsearch import Elasticsearch, helpers
from llama_index.core.schema import BaseNode, MetadataMode

from config.settings import settings

log = logging.getLogger(__name__)

_client: Elasticsearch | None = None

# 索引mapping：content全文检索；file_key/node_id为keyword，用于精确删除与定位；
# metadata动态存储提取器产出的元数据（标题/摘要/关键词/实体等）
_INDEX_MAPPING = {
    'properties': {
        'content': {'type': 'text'},
        'file_key': {'type': 'keyword'},
        'node_id': {'type': 'keyword'},
        'metadata': {'type': 'object', 'dynamic': True},
    }
}


def _get_client() -> Elasticsearch:
    """惰性创建全局ES客户端（进程内复用连接池）"""
    global _client
    if _client is None:
        auth = (settings.ES_USERNAME, settings.ES_PASSWORD) if settings.ES_USERNAME else None
        _client = Elasticsearch(settings.ES_URL, basic_auth=auth,
                                request_timeout=settings.ES_REQUEST_TIMEOUT)
    return _client


def _ensure_index(index_name: str) -> None:
    """索引不存在时按默认mapping创建"""
    client = _get_client()
    if not client.indices.exists(index=index_name):
        client.indices.create(index=index_name, mappings=_INDEX_MAPPING)


def index_nodes(index_name: str, nodes: list[BaseNode]) -> int:
    """批量写入分块文档（doc id=node_id，重复写入自动覆盖），返回写入条数

    content取节点原文（不含元数据），元数据单独存metadata字段供过滤展示。
    """
    _ensure_index(index_name)
    actions = [
        {
            '_op_type': 'index',
            '_index': index_name,
            '_id': node.node_id,
            '_source': {
                'node_id': node.node_id,
                'file_key': node.ref_doc_id,
                'content': node.get_content(MetadataMode.NONE),
                'metadata': node.metadata,
            },
        }
        for node in nodes
    ]
    helpers.bulk(_get_client(), actions)
    return len(actions)


def delete_chunks(index_name: str, file_key: str) -> None:
    """按file_key删除该文件的全部分块（索引不存在时静默跳过）"""
    client = _get_client()
    if not client.indices.exists(index=index_name):
        return
    client.delete_by_query(
        index=index_name, query={'term': {'file_key': file_key}}, refresh=True)


def drop_index(index_name: str) -> None:
    """删除整个索引，一次性清理该库全部全文数据（不存在时静默跳过）"""
    client = _get_client()
    if client.indices.exists(index=index_name):
        client.indices.delete(index=index_name)


def _filter_clause(field: str, op: str, value) -> dict:
    """单条过滤条件 → ES query子句（file_key为顶层keyword字段，其余在metadata下）"""
    es_field = field if field == 'file_key' else f'metadata.{field}'
    if op == 'in':
        return {'terms': {es_field: list(value)}}
    if op in ('gt', 'gte', 'lt', 'lte'):
        return {'range': {es_field: {op: value}}}
    if op == 'contains':
        return {'wildcard': {es_field: {'value': f'*{value}*'}}}
    return {'term': {es_field: value}}


def search(index_name: str, query: str, filters: list[dict] | None = None,
           top_k: int = 20) -> list[dict]:
    """BM25全文检索（阻塞，须在线程中执行）

    filters 为规范化过滤条件列表 [{field, op, value}]；query为空时match_all。
    返回 [{node_id, file_key, content, metadata, score}]。
    """
    client = _get_client()
    if not client.indices.exists(index=index_name):
        return []
    must = [{'match': {'content': {'query': query}}}] if query else [{'match_all': {}}]
    body = {'bool': {'must': must, 'filter': [
        _filter_clause(f['field'], f['op'], f['value']) for f in (filters or [])]}}
    resp = client.search(index=index_name, query=body, size=top_k)
    return [
        {
            'node_id': hit['_id'],
            'file_key': src.get('file_key'),
            'content': src.get('content'),
            'metadata': src.get('metadata') or {},
            'score': float(hit.get('_score') or 0),
        }
        for hit in resp.get('hits', {}).get('hits', [])
        for src in [hit.get('_source') or {}]
    ]
