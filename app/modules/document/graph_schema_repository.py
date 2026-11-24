"""知识库图谱schema数据访问层：kb_graph_schemas 单表读写（每库一份）

出参统一序列化为前端契约（camelCase）：见 web/src/types/knowledge.ts。
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select

from core.dependencies import get_db_session
from db.pg.orm_models import KbGraphSchema


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _to_dict(row: KbGraphSchema) -> dict:
    schema = row.schema or {}
    return {
        'kbId': str(row.kb_id),
        'entities': schema.get('entities') or [],
        'relations': schema.get('relations') or [],
        'createdAt': _iso(row.created_at),
        'updatedAt': _iso(row.updated_at),
    }


async def get_schema(kb_id: int) -> Optional[dict]:
    """读取知识库图谱schema（未创建返回None）"""
    async with get_db_session() as session:
        row = (await session.execute(
            select(KbGraphSchema).where(KbGraphSchema.kb_id == kb_id)
        )).scalar_one_or_none()
        return _to_dict(row) if row else None


async def schema_exists(kb_id: int) -> bool:
    async with get_db_session() as session:
        return (await session.execute(
            select(KbGraphSchema.id).where(KbGraphSchema.kb_id == kb_id)
        )).scalar_one_or_none() is not None


async def save_schema(kb_id: int, schema: dict) -> dict:
    """整体覆盖保存知识库图谱schema（upsert），返回保存后的schema"""
    async with get_db_session() as session:
        row = (await session.execute(
            select(KbGraphSchema).where(KbGraphSchema.kb_id == kb_id)
        )).scalar_one_or_none()
        if row:
            row.schema = schema
        else:
            row = KbGraphSchema(kb_id=kb_id, schema=schema)
            session.add(row)
        await session.flush()
        await session.refresh(row)
        return _to_dict(row)


async def delete_by_kb(kb_id: int) -> int:
    """删除知识库图谱schema（知识库级联删除时调用）"""
    async with get_db_session() as session:
        result = await session.execute(
            delete(KbGraphSchema).where(KbGraphSchema.kb_id == kb_id))
        await session.commit()
        return result.rowcount
