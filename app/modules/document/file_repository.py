"""知识库文件数据访问层：kb_files 单表读写

出参统一序列化为前端契约（camelCase + 字符串id），见 web/src/types/knowledge.ts。
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, func, select, update

from core.dependencies import get_db_session
from db.pg.orm_models import FileParseStrategy, KbFile, LlamaDocstoreNode

FILE_STATUS_PROCESSING = 'processing'  # 解析中
FILE_STATUS_INDEXED = 'indexed'  # 已索引
FILE_STATUS_FAILED = 'failed'  # 解析失败


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _file_to_dict(f: KbFile, strategy_name: Optional[str] = None) -> dict:
    return {
        'id': str(f.id),
        'kbId': str(f.kb_id),
        'name': f.file_name,
        'size': f.size,
        'chunkCount': f.chunk_count or 0,
        'status': f.status,
        'error': f.error,
        'strategyId': str(f.strategy_id) if f.strategy_id else None,
        'strategyName': strategy_name,
        'objectName': f.object_name,
        'contentType': f.content_type,
        'uploadedBy': str(f.uploaded_by),
        'createdAt': _iso(f.created_at),
        'updatedAt': _iso(f.updated_at),
    }


async def create_file(
    kb_id: int, file_name: str, object_name: str, bucket: str, size: int,
    content_type: str, strategy_id: Optional[int], uploaded_by: int,
) -> dict:
    async with get_db_session() as session:
        record = KbFile(
            kb_id=kb_id, file_name=file_name, object_name=object_name, bucket=bucket,
            size=size, content_type=content_type, strategy_id=strategy_id,
            status=FILE_STATUS_PROCESSING, uploaded_by=uploaded_by,
        )
        session.add(record)
        await session.flush()
        await session.refresh(record)
        return _file_to_dict(record)


async def list_files(kb_id: int) -> list[dict]:
    """知识库内文件列表（左联策略表带出策略名），按更新时间倒序"""
    async with get_db_session() as session:
        rows = (await session.execute(
            select(KbFile, FileParseStrategy.strategy_name)
            .join(FileParseStrategy, FileParseStrategy.id == KbFile.strategy_id, isouter=True)
            .where(KbFile.kb_id == kb_id)
            .order_by(KbFile.updated_at.desc(), KbFile.id.desc())
        )).all()
        return [_file_to_dict(f, strategy_name=name) for f, name in rows]


async def get_file(file_id: int) -> Optional[dict]:
    async with get_db_session() as session:
        row = (await session.execute(
            select(KbFile, FileParseStrategy.strategy_name)
            .join(FileParseStrategy, FileParseStrategy.id == KbFile.strategy_id, isouter=True)
            .where(KbFile.id == file_id)
        )).first()
        if not row:
            return None
        f, name = row
        return _file_to_dict(f, strategy_name=name)


async def mark_status(
    file_id: int, status: str, chunk_count: Optional[int] = None, error: Optional[str] = None,
) -> None:
    """任务worker回写解析状态（成功带分块数，失败带原因）"""
    fields: dict = {'status': status}
    if chunk_count is not None:
        fields['chunk_count'] = chunk_count
    if error is not None:
        fields['error'] = error
    async with get_db_session() as session:
        await session.execute(update(KbFile).where(KbFile.id == file_id).values(**fields))


async def delete_file(file_id: int) -> bool:
    """删除kb_files记录（记录不存在时返回False）"""
    async with get_db_session() as session:
        result = await session.execute(delete(KbFile).where(KbFile.id == file_id))
        await session.commit()
        return result.rowcount > 0


async def delete_files_by_kb(kb_id: int) -> int:
    """批量删除知识库下全部文件记录（MinIO对象/任务/向量由service先行级联清理）"""
    async with get_db_session() as session:
        result = await session.execute(delete(KbFile).where(KbFile.kb_id == kb_id))
        await session.commit()
        return result.rowcount


async def count_by_strategy(kb_id: int) -> dict[int, int]:
    """按策略聚合文件数（策略列表documentCount展示用）"""
    async with get_db_session() as session:
        rows = (await session.execute(
            select(KbFile.strategy_id, func.count(KbFile.id))
            .where(KbFile.kb_id == kb_id, KbFile.strategy_id.isnot(None))
            .group_by(KbFile.strategy_id)
        )).all()
        return {strategy_id: count for strategy_id, count in rows}


async def list_file_chunks(file_id: int, page: int, page_size: int) -> dict:
    """文件分块预览：按ref_doc_id=file:{file_id}查docstore切分节点（分页）

    node_json为doc_to_json产物（含text/metadata），仅取文本块（源文档hash行node_json为NULL）。
    顺序按created_at+node_id（node_id为随机UUID，跨次解析重跑后次序可能变化）。
    """
    file_key = f'file:{file_id}'
    async with get_db_session() as session:
        conditions = (
            LlamaDocstoreNode.ref_doc_id == file_key,
            LlamaDocstoreNode.node_json.isnot(None),
        )
        total = (await session.execute(
            select(func.count()).select_from(LlamaDocstoreNode).where(*conditions)
        )).scalar()
        rows = (await session.execute(
            select(LlamaDocstoreNode.node_json, LlamaDocstoreNode.created_at)
            .where(*conditions)
            .order_by(LlamaDocstoreNode.created_at, LlamaDocstoreNode.node_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).all()

    chunks = [
        {
            'nodeId': node_json['id_'],
            'text': node_json.get('text') or '',
            'metadata': node_json.get('metadata') or {},
            'createdAt': _iso(created_at),
        }
        for (node_json, created_at) in rows
    ]
    return {'total': int(total or 0), 'chunks': chunks}
