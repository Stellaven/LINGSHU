"""知识库图谱schema业务层：每库一份实体/关系类型定义的查询与整体保存

权限：仅知识库所属项目的成员可操作（复用团队域成员校验）。
策略开启构建图谱（graph=True）时要求本schema已创建，schema本身仅在「图谱schema」页签维护。
"""

from typing import Optional

import logging

from core.exceptions import BusinessError
from modules.document import graph_schema_repository, strategy_repository
from modules.team import repository as team_repository
from modules.team.constants import (
    CODE_NOT_PROJECT_MEMBER,
    CODE_PROJECT_KB_NOT_FOUND,
)

# schema规模上限
MAX_ENTITIES = 50
MAX_RELATIONS = 100
MAX_PROPERTIES_PER_ENTITY = 50

log = logging.getLogger(__name__)


async def _require_kb_member(kb_id: int, user_id: int) -> None:
    """知识库须存在且当前用户须为其所属项目的成员"""
    kb = await strategy_repository.get_knowledge_base(kb_id)
    if not kb:
        raise BusinessError('知识库不存在', code=CODE_PROJECT_KB_NOT_FOUND, status_code=404)
    if not await team_repository.is_project_member(kb['projectId'], user_id):
        raise BusinessError('尚不是项目成员', code=CODE_NOT_PROJECT_MEMBER, status_code=403)


def _validate_schema(entities: list[dict], relations: list[dict]) -> None:
    """校验schema定义：实体/关系名唯一、关系subject/object须指向已定义实体类型"""
    if not entities:
        raise BusinessError('图谱schema至少需要定义一个实体类型', code=40010, status_code=400)
    if len(entities) > MAX_ENTITIES:
        raise BusinessError(f'实体类型最多 {MAX_ENTITIES} 个', code=40010, status_code=400)
    if len(relations) > MAX_RELATIONS:
        raise BusinessError(f'关系类型最多 {MAX_RELATIONS} 条', code=40010, status_code=400)

    entity_names = set()
    for entity in entities:
        name = (entity.get('name') or '').strip()
        if not name:
            raise BusinessError('实体类型名不能为空', code=40010, status_code=400)
        if name in entity_names:
            raise BusinessError(f'实体类型「{name}」重复定义', code=40010, status_code=400)
        entity_names.add(name)
        properties = entity.get('properties') or {}
        if len(properties) > MAX_PROPERTIES_PER_ENTITY:
            raise BusinessError(
                f'实体类型「{name}」属性最多 {MAX_PROPERTIES_PER_ENTITY} 个',
                code=40010, status_code=400)
        for prop_name, prop_desc in properties.items():
            if not str(prop_name).strip():
                raise BusinessError(
                    f'实体类型「{name}」存在空的属性名', code=40010, status_code=400)
            if not isinstance(prop_desc, str):
                raise BusinessError(
                    f'实体类型「{name}」属性 {prop_name} 的描述须为字符串',
                    code=40010, status_code=400)

    relation_names = set()
    for relation in relations:
        name = (relation.get('name') or '').strip()
        subject = (relation.get('subjectType') or '').strip()
        object_ = (relation.get('objectType') or '').strip()
        if not name:
            raise BusinessError('关系类型名不能为空', code=40010, status_code=400)
        if name in relation_names:
            raise BusinessError(f'关系类型「{name}」重复定义', code=40010, status_code=400)
        relation_names.add(name)
        if subject not in entity_names or object_ not in entity_names:
            raise BusinessError(
                f'关系「{name}」的起点/终点（{subject}→{object_}）必须为已定义的实体类型',
                code=40010, status_code=400)


async def get_graph_schema(kb_id: int, user_id: int) -> Optional[dict]:
    """查询知识库图谱schema（未创建返回None）"""
    await _require_kb_member(kb_id, user_id)
    return await graph_schema_repository.get_schema(kb_id)


async def save_graph_schema(kb_id: int, user_id: int, entities: list, relations: list) -> dict:
    """整体覆盖保存知识库图谱schema（创建与修改共用），并同步注册到KAG项目SPG schema

    同步注册为尽力而为：先调KAG接口确保project已创建（幂等），再注册实体/关系类型；
    KAG侧失败不阻断本地保存（仅告警，构图时仍会按最新schema重试注册）。
    """
    await _require_kb_member(kb_id, user_id)
    _validate_schema(entities, relations)
    schema = {'entities': entities, 'relations': relations}
    result = await graph_schema_repository.save_schema(kb_id, schema)
    try:
        from modules.document import kag_store
        await kag_store.sync_schema_to_kag(kb_id, result)
    except Exception:
        log.warning('图谱schema注册到KAG失败（不影响本地保存）: kb_id=%s', kb_id, exc_info=True)
    return result
