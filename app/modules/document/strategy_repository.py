"""文件处理策略数据访问层：file_parse_strategies 单表读写

出参统一序列化为前端契约（camelCase + 字符串id），见 web/src/types/knowledge.ts。
文档引用数（documentCount）由 kb_files 按 strategy_id 实时聚合，见 file_repository.count_by_strategy。
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, func, select, update

from core.dependencies import get_db_session
from db.pg.orm_models import FileParseStrategy, ProjectKnowledgeBase, TeamProject
from modules.document import file_repository


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


EMPTY_STAGES = {"parser": [], "pre_extract": [], "split": [], "post_extract": []}


def _strategy_to_dict(strategy: FileParseStrategy, document_count: int = 0) -> dict:
    stages = strategy.stages or dict(EMPTY_STAGES)
    return {
        'id': str(strategy.id),
        'kbId': str(strategy.kb_id),
        'name': strategy.strategy_name,
        'embedModel': strategy.embed_model,
        # 编排序列：解析 → 前置提取 → 分块 → 后置提取，执行顺序即 transformations 顺序
        'stages': stages,
        'graph': strategy.graph,
        # 引用该策略的文件数（kb_files聚合）
        'documentCount': document_count,
        'createdAt': _iso(strategy.created_at),
        'updatedAt': _iso(strategy.updated_at),
    }


async def get_knowledge_base(kb_id: int) -> Optional[dict]:
    """知识库归属信息（校验存在性与项目成员权限用）"""
    async with get_db_session() as session:
        row = (await session.execute(
            select(ProjectKnowledgeBase.id, ProjectKnowledgeBase.project_id, TeamProject.team_id)
            .join(TeamProject, TeamProject.id == ProjectKnowledgeBase.project_id)
            .where(ProjectKnowledgeBase.id == kb_id)
        )).first()
        if not row:
            return None
        return {'id': row[0], 'projectId': row[1], 'teamId': row[2]}


async def strategy_name_exists(kb_id: int, name: str, except_id: Optional[int] = None) -> bool:
    """策略名知识库内唯一（编辑时排除自身）"""
    async with get_db_session() as session:
        stmt = select(FileParseStrategy.id).where(
            FileParseStrategy.kb_id == kb_id, FileParseStrategy.strategy_name == name)
        if except_id is not None:
            stmt = stmt.where(FileParseStrategy.id != except_id)
        return (await session.execute(stmt)).scalar_one_or_none() is not None


async def create_strategy(
    kb_id: int, name: str, embed_model: str, graph: bool, stages: dict,
) -> dict:
    async with get_db_session() as session:
        strategy = FileParseStrategy(
            kb_id=kb_id, strategy_name=name, embed_model=embed_model,
            stages=stages, graph=graph,
        )
        session.add(strategy)
        await session.flush()
        await session.refresh(strategy)
        return _strategy_to_dict(strategy)


async def list_strategies(kb_id: int) -> list[dict]:
    """知识库内策略列表，按更新时间倒序"""
    async with get_db_session() as session:
        rows = (await session.execute(
            select(FileParseStrategy)
            .where(FileParseStrategy.kb_id == kb_id)
            .order_by(FileParseStrategy.updated_at.desc(), FileParseStrategy.id.desc())
        )).scalars().all()
    counts = await file_repository.count_by_strategy(kb_id)
    return [_strategy_to_dict(s, counts.get(s.id, 0)) for s in rows]


async def get_strategy(kb_id: int, strategy_id: int) -> Optional[dict]:
    async with get_db_session() as session:
        strategy = (await session.execute(
            select(FileParseStrategy).where(
                FileParseStrategy.kb_id == kb_id, FileParseStrategy.id == strategy_id)
        )).scalar_one_or_none()
        if not strategy:
            return None
    counts = await file_repository.count_by_strategy(kb_id)
    return _strategy_to_dict(strategy, counts.get(strategy.id, 0))


async def update_strategy(kb_id: int, strategy_id: int, fields: dict) -> Optional[dict]:
    """按提交字段更新（fields 键为 ORM 列名，已由 service 层校验）"""
    async with get_db_session() as session:
        stmt = (
            update(FileParseStrategy)
            .where(FileParseStrategy.kb_id == kb_id, FileParseStrategy.id == strategy_id)
            .values(**fields)
        )
        result = await session.execute(stmt)
        if result.rowcount == 0:
            return None
        strategy = await session.get(FileParseStrategy, strategy_id)
        await session.refresh(strategy)
    counts = await file_repository.count_by_strategy(kb_id)
    return _strategy_to_dict(strategy, counts.get(strategy.id, 0))


async def delete_strategy(kb_id: int, strategy_id: int) -> bool:
    async with get_db_session() as session:
        result = await session.execute(delete(FileParseStrategy).where(
            FileParseStrategy.kb_id == kb_id, FileParseStrategy.id == strategy_id))
        return result.rowcount > 0


async def delete_by_kb(kb_id: int) -> int:
    """删除知识库下全部处理策略（知识库级联删除时调用）"""
    async with get_db_session() as session:
        result = await session.execute(delete(FileParseStrategy).where(FileParseStrategy.kb_id == kb_id))
        await session.commit()
        return result.rowcount
