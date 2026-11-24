"""团队域业务逻辑：建团/建项目/团队与成员/项目查询

权限规则：
  - 建团：任何登录用户，创建者即所有者；
  - 成员/项目查询与建项目：需为本团队成员（所有成员可查，owner才可建项目由前端控制展示，
    后端统一放宽为成员可建，与mock语义一致）；
  - 解散团队：仅团队所有者；解散项目：仅项目负责人；删除知识库：项目成员。
"""

import logging

from core.exceptions import BusinessError
from modules.team import repository
from modules.team.constants import (
    CODE_ACCOUNT_NOT_FOUND,
    CODE_MEMBER_EXISTS,
    CODE_NOT_PROJECT_MEMBER,
    CODE_OWNER_NOT_MEMBER,
    CODE_PROJECT_KB_NAME_CONFLICT,
    CODE_PROJECT_KB_NOT_FOUND,
    CODE_PROJECT_NOT_FOUND,
    CODE_NOT_TEAM_MEMBER,
    CODE_TARGET_NOT_TEAM_MEMBER,
    CODE_TEAM_NOT_FOUND,
)

log = logging.getLogger(__name__)

NAME_REQUIRED_MSG = '名称不能为空'


async def create_team(user_id: int, account: str, name: str, description: str) -> dict:
    name = (name or '').strip()
    description = (description or '').strip()
    if not name:
        raise BusinessError(NAME_REQUIRED_MSG, code=40008, status_code=400)
    return await repository.create_team(user_id, account, name, description)


async def list_teams(user_id: int) -> list[dict]:
    return await repository.list_teams_for_user(user_id)


async def _require_member(team_id: int, user_id: int) -> None:
    """团队须存在且当前用户须为成员，否则抛业务异常"""
    if not await repository.get_team(team_id):
        raise BusinessError('团队不存在', code=CODE_TEAM_NOT_FOUND, status_code=404)
    if not await repository.get_member_by_user(team_id, user_id):
        raise BusinessError('尚未加入该团队', code=CODE_NOT_TEAM_MEMBER, status_code=403)


async def get_my_membership(team_id: int, user_id: int) -> dict:
    await _require_member(team_id, user_id)
    return await repository.get_member_by_user(team_id, user_id)


async def list_members(team_id: int, user_id: int, page: int, page_size: int,
                       query: str = '') -> dict:
    await _require_member(team_id, user_id)
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    return await repository.list_members(team_id, page, page_size, (query or '').strip())


async def add_member(team_id: int, user_id: int, account: str) -> dict:
    """添加团队成员（团队成员可添加，目标须为系统账号且未加入本团队）"""
    await _require_member(team_id, user_id)
    account = (account or '').strip()
    if not account:
        raise BusinessError('账号不能为空', code=40008, status_code=400)
    target = await repository.get_system_user_by_account(account)
    if not target:
        raise BusinessError('账号不存在', code=CODE_ACCOUNT_NOT_FOUND, status_code=404)
    if await repository.get_member_by_user(team_id, int(target['id'])):
        raise BusinessError('该成员已在团队中', code=CODE_MEMBER_EXISTS, status_code=409)
    return await repository.add_member(team_id, int(target['id']), target['account'])


async def create_project(team_id: int, user_id: int, account: str,
                         name: str, description: str, owner_account: str | None) -> dict:
    name = (name or '').strip()
    description = (description or '').strip()
    if not name:
        raise BusinessError(NAME_REQUIRED_MSG, code=40008, status_code=400)
    await _require_member(team_id, user_id)

    # 负责人：缺省为创建者；指定时须为本团队成员
    if owner_account:
        owner_member = await repository.get_member_by_account(team_id, owner_account.strip())
        if not owner_member:
            raise BusinessError('项目负责人不在本团队中', code=CODE_OWNER_NOT_MEMBER, status_code=400)
    else:
        owner_member = await repository.get_member_by_user(team_id, user_id)

    return await repository.create_project(
        team_id, name, description, owner_member, creator_user_id=user_id, creator_account=account,
    )


async def list_projects(team_id: int, user_id: int) -> list[dict]:
    await _require_member(team_id, user_id)
    return await repository.list_projects(team_id)


async def _require_project_member(project_id: int, user_id: int) -> None:
    """项目须存在且当前用户须为项目成员，否则抛业务异常"""
    if not await repository.project_exists(project_id):
        raise BusinessError('项目不存在', code=CODE_PROJECT_NOT_FOUND, status_code=404)
    if not await repository.is_project_member(project_id, user_id):
        raise BusinessError('尚不是项目成员', code=CODE_NOT_PROJECT_MEMBER, status_code=403)


async def list_project_members(project_id: int, user_id: int, page: int, page_size: int,
                               query: str = '') -> dict:
    """项目成员分页列表（仅项目成员可查）"""
    await _require_project_member(project_id, user_id)
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    return await repository.list_project_members(project_id, page, page_size, (query or '').strip())


async def add_project_member(project_id: int, user_id: int, account: str) -> dict:
    """添加项目成员（项目成员可添加，目标须为团队成员且未加入本项目）"""
    await _require_project_member(project_id, user_id)
    account = (account or '').strip()
    if not account:
        raise BusinessError('账号不能为空', code=40008, status_code=400)
    project = await repository.get_project(project_id)
    if not project:
        raise BusinessError('项目不存在', code=CODE_PROJECT_NOT_FOUND, status_code=404)
    target = await repository.get_system_user_by_account(account)
    if not target:
        raise BusinessError('账号不存在', code=CODE_ACCOUNT_NOT_FOUND, status_code=404)
    team_member = await repository.get_member_by_user(int(project['teamId']), int(target['id']))
    if not team_member:
        raise BusinessError('该账号不是团队成员', code=CODE_TARGET_NOT_TEAM_MEMBER, status_code=400)
    if await repository.get_project_member_by_user(project_id, int(target['id'])):
        raise BusinessError('该成员已在项目中', code=CODE_MEMBER_EXISTS, status_code=409)
    return await repository.add_project_member(
        project_id, int(target['id']), target['account'], nickname=team_member['nickname'],
    )


async def list_project_knowledge_bases(project_id: int, user_id: int) -> list[dict]:
    """项目知识库列表（按自定义排序）"""
    await _require_project_member(project_id, user_id)
    return await repository.list_project_knowledge_bases(project_id)


async def get_project(project_id: int, user_id: int) -> dict:
    """项目详情：团队成员可查看（进入项目后由 members/me 自动补项目成员身份）"""
    project = await repository.get_project(project_id)
    if not project:
        raise BusinessError('项目不存在', code=CODE_PROJECT_NOT_FOUND, status_code=404)
    if not await repository.get_member_by_user(int(project['teamId']), user_id):
        raise BusinessError('尚未加入该团队', code=CODE_NOT_TEAM_MEMBER, status_code=403)
    return project


async def get_my_project_membership(project_id: int, user_id: int, account: str) -> dict:
    """我的项目成员信息；非项目成员的团队成员首次进入时自动加入（与mock语义一致）"""
    project = await repository.get_project(project_id)
    if not project:
        raise BusinessError('项目不存在', code=CODE_PROJECT_NOT_FOUND, status_code=404)
    member = await repository.get_project_member_by_user(project_id, user_id)
    if member:
        return member
    if not await repository.get_member_by_user(int(project['teamId']), user_id):
        raise BusinessError('尚未加入该团队', code=CODE_NOT_TEAM_MEMBER, status_code=403)
    return await repository.join_project(project_id, user_id, account)


async def get_project_knowledge_base(kb_id: int, user_id: int) -> dict:
    """知识库详情（项目成员可查，附带所属团队ID）"""
    kb = await repository.get_project_knowledge_base(kb_id)
    if not kb:
        raise BusinessError('知识库不存在', code=CODE_PROJECT_KB_NOT_FOUND, status_code=404)
    await _require_project_member(int(kb['projectId']), user_id)
    return kb


async def create_project_knowledge_base(
    project_id: int, user_id: int, name: str, description: str, embed_model: str = 'bge-m3',
) -> dict:
    """新建项目知识库（知识库名项目内唯一）"""
    name = (name or '').strip()
    description = (description or '').strip()
    if not name:
        raise BusinessError(NAME_REQUIRED_MSG, code=40008, status_code=400)
    await _require_project_member(project_id, user_id)
    if await repository.project_kb_name_exists(project_id, name):
        raise BusinessError('该项目下已存在同名知识库', code=CODE_PROJECT_KB_NAME_CONFLICT, status_code=409)
    return await repository.create_project_knowledge_base(project_id, name, description, embed_model)


# ---------------- 级联删除：解散团队/项目、删除知识库 ----------------

async def _purge_knowledge_base_data(kb_id: int) -> None:
    """级联清理知识库全部数据（不校验权限，由入口处统一校验）：

    解析任务(Redis)→MinIO对象→分块(PG docstore)→向量(Milvus collection整体drop)
    →处理策略→文件记录→知识库记录。
    """
    from modules.document import file_repository as document_file_repository
    from modules.document import service as document_service
    from modules.document import strategy_repository
    from modules.task.backend import get_task_backend
    from utils import file_utils

    kb_id = int(kb_id)
    backend = get_task_backend()
    for f in await document_file_repository.list_files(kb_id):
        # 先摘除解析任务，防止删除后任务仍被消费重放
        await backend.purge_file_jobs(f['id'])
        # MinIO对象（不存在时静默成功）
        await file_utils.delete_file(f['objectName'])
        # PG docstore分块；向量由下方collection级drop一次性清理
        file_key = document_service.build_file_key(f['id'], f['objectName'])
        await document_service.delete_file_docstore_chunks(file_key)
    await document_service.drop_kb_collection(kb_id)
    await strategy_repository.delete_by_kb(kb_id)
    from modules.document import graph_schema_repository
    await graph_schema_repository.delete_by_kb(kb_id)
    await document_file_repository.delete_files_by_kb(kb_id)
    await repository.delete_knowledge_base(kb_id)
    log.info("知识库级联删除完成: kb_id=%s", kb_id)


async def delete_knowledge_base(kb_id: int, user_id: int) -> None:
    """删除知识库（项目成员可删），级联清理文件/策略/向量/解析任务等全部数据"""
    kb = await repository.get_project_knowledge_base(kb_id)
    if not kb:
        raise BusinessError('知识库不存在', code=CODE_PROJECT_KB_NOT_FOUND, status_code=404)
    await _require_project_member(int(kb['projectId']), user_id)
    await _purge_knowledge_base_data(kb_id)


async def delete_project(project_id: int, user_id: int) -> None:
    """解散项目（仅项目负责人）：逐级删除项目下知识库及其文件数据后删除项目"""
    project = await repository.get_project(project_id)
    if not project:
        raise BusinessError('项目不存在', code=CODE_PROJECT_NOT_FOUND, status_code=404)
    me = await repository.get_project_member_by_user(project_id, user_id)
    if not me or me['role'] != 'owner':
        raise BusinessError('仅项目负责人可解散项目', code=CODE_NOT_PROJECT_MEMBER, status_code=403)
    for kb in await repository.list_project_knowledge_bases(project_id):
        await _purge_knowledge_base_data(int(kb['id']))
    await repository.delete_project(project_id)
    log.info("项目已解散: project_id=%s operator=%s", project_id, user_id)


async def delete_team(team_id: int, user_id: int) -> None:
    """解散团队（仅团队所有者）：逐级删除团队下项目→知识库→文件数据后删除团队"""
    if not await repository.get_team(team_id):
        raise BusinessError('团队不存在', code=CODE_TEAM_NOT_FOUND, status_code=404)
    member = await repository.get_member_by_user(team_id, user_id)
    if not member or member['role'] != 'owner':
        raise BusinessError('仅团队所有者可解散团队', code=CODE_NOT_TEAM_MEMBER, status_code=403)
    for project in await repository.list_projects(team_id):
        project_id = int(project['id'])
        for kb in await repository.list_project_knowledge_bases(project_id):
            await _purge_knowledge_base_data(int(kb['id']))
        await repository.delete_project(project_id)
    await repository.delete_team(team_id)
    log.info("团队已解散: team_id=%s operator=%s", team_id, user_id)
