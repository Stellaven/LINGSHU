"""Milvus 向量存储操作封装

service.py 只调用本模块暴露的函数，不直接操作 Milvus SDK / llama-index：
- vector_store：构建 llama-index MilvusVectorStore（IngestionPipeline 写入用）
- delete_chunks：按 doc_id 删除文件分块向量
- drop_collection：删除整个 collection（整库清理用）
"""

from llama_index.vector_stores.milvus import MilvusVectorStore
from pymilvus import MilvusClient

from config.settings import settings


def vector_store(collection_name: str, overwrite: bool = False) -> MilvusVectorStore:
    """构建Milvus向量存储（连接与维度参数统一从settings读取）"""
    return MilvusVectorStore(
        uri=settings.MILVUS_URI, dim=settings.MILVUS_DIM,
        collection_name=collection_name, overwrite=overwrite,
    )


def delete_chunks(collection_name: str, doc_ids: str | list[str]) -> None:
    """按doc_id删除分块向量（collection不存在时静默跳过）

    直接用MilvusClient按需连接，避免经MilvusVectorStore构造时
    把不存在的collection先建出来。doc_id为llama-index写入时
    的源文档标识（即file_key），字段名与MilvusVectorStore默认schema一致。
    """
    if isinstance(doc_ids, str):
        doc_ids = [doc_ids]
    client = MilvusClient(uri=settings.MILVUS_URI)
    if client.has_collection(collection_name):
        quoted = ','.join(f'"{doc_id}"' for doc_id in doc_ids)
        client.delete(collection_name, filter=f'doc_id in [{quoted}]')


def drop_collection(collection_name: str) -> None:
    """删除整个collection，一次性清理该库全部向量数据（不存在时静默跳过）"""
    client = MilvusClient(uri=settings.MILVUS_URI)
    if client.has_collection(collection_name):
        client.drop_collection(collection_name)


def _filter_expr(filters: list[dict] | None) -> str:
    """规范化过滤条件列表 [{field, op, value}] → Milvus expr

    file_key 对应写入时的源文档标识字段doc_id；其余字段为元数据动态字段。
    """
    clauses = []
    for f in (filters or []):
        field = 'doc_id' if f['field'] == 'file_key' else f['field']
        op, value = f['op'], f['value']
        if op == 'in':
            values = ','.join(f'"{v}"' if isinstance(v, str) else str(v) for v in value)
            clauses.append(f'{field} in [{values}]')
        elif op == 'contains':
            clauses.append(f"TEXT_MATCH({field}, '{value}')")
        elif isinstance(value, str):
            clauses.append(f'{field} == "{value}"')
        else:
            symbol = {'eq': '==', 'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<='}[op]
            clauses.append(f'{field} {symbol} {value}')
    return ' and '.join(clauses)


def search(collection_name: str, query_vector: list, filters: list[dict] | None = None,
           top_k: int | None = None) -> list[dict]:
    """向量相似度检索（阻塞，须在线程中执行）

    query_vector 为查询向量（与写入embedding同模型同维度）。
    返回 [{node_id, file_key, content, metadata, score}]，score为相似度（越大越相似）。
    """
    client = MilvusClient(uri=settings.MILVUS_URI)
    if not client.has_collection(collection_name):
        return []
    results = client.search(
        collection_name, data=[query_vector], filter=_filter_expr(filters),
        limit=top_k or settings.RETRIEVAL_TOP_K, output_fields=['*'],
    )
    items = []
    for hits in results:
        for hit in hits or []:
            entity = hit.get('entity') or {}
            items.append({
                'node_id': str(hit.get('id')),
                'file_key': entity.get('doc_id'),
                'content': entity.get('text'),
                'metadata': {k: v for k, v in entity.items()
                             if k not in ('text', 'doc_id', 'pk', 'id', 'embedding')},
                'score': float(hit.get('distance') or 0),
            })
    return items
