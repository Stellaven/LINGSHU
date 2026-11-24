"""团队模块接口：建团/团队列表/成员列表/我的成员信息/建项目/项目列表
                项目维度：项目详情/项目成员列表/我的项目成员信息/项目知识库列表/新建项目知识库

除公开路径外统一经 AuthMiddleware 鉴权，request.state 注入 user_id/account。
"""

import logging

from fastapi import APIRouter, Query, Request

from common.response import ResponseObject
from modules.auth import service as auth_service
from modules.team import service
from modules.team.schema import (
    AddMemberRequest,
    CreateProjectKnowledgeBaseRequest,
    CreateProjectRequest,
    CreateTeamRequest,
)

api = APIRouter(prefix="/teams")
# 项目维度资源路由（前端契约：/api/projects/{projectId}/...）
project_api = APIRouter(prefix="/projects")
# 知识库维度资源路由（前端契约：/api/knowledge-bases/{kbId}/...）
kb_api = APIRouter(prefix="/knowledge-bases")
# 系统账号维度资源路由（前端契约：/api/accounts/...）
account_api = APIRouter(prefix="/accounts")

log = logging.getLogger(__name__)


@account_api.get('/search')
async def search_accounts(
    request: Request,
    query: str = Query(default='', max_length=64),
):
    """搜索系统账号（添加成员选人用，仅返回正常状态账号，按账号模糊匹配）"""
    users = await auth_service.search_accounts(query)
    return ResponseObject(data=users)


@api.post('/create')
async def create_team(req: CreateTeamRequest, request: Request):
    """新建团队，创建者成为团队所有者"""
    user_id = request.state.user_id
    account = request.state.account
    log.info("新建团队: user_id=%s name=%s", user_id, req.name)
    team = await service.create_team(user_id, account, req.name, req.description)
    return ResponseObject(data=team)


@api.post('/list')
async def list_teams(request: Request):
    """我参与的团队列表（含我的角色）"""
    teams = await service.list_teams(request.state.user_id)
    return ResponseObject(data=teams)


@api.get('/{team_id}/members/me')
async def my_membership(team_id: int, request: Request):
    """我在团队中的成员信息"""
    member = await service.get_my_membership(team_id, request.state.user_id)
    return ResponseObject(data=member)


@api.get('/{team_id}/members')
async def list_members(
    team_id: int,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    query: str = Query(default='', max_length=64),
):
    """团队成员分页列表（所有者置顶，支持昵称/账号模糊搜索）"""
    result = await service.list_members(
        team_id, request.state.user_id, page, page_size, query,
    )
    return ResponseObject(data=result)


@api.post('/{team_id}/members/add')
async def add_member(team_id: int, req: AddMemberRequest, request: Request):
    """添加团队成员（团队成员可添加，目标须为系统账号）"""
    log.info("添加团队成员: user_id=%s team_id=%s account=%s",
             request.state.user_id, team_id, req.account)
    member = await service.add_member(team_id, request.state.user_id, req.account)
    return ResponseObject(data=member)


@api.post('/{team_id}/projects/create')
async def create_project(team_id: int, req: CreateProjectRequest, request: Request):
    """新建项目，负责人缺省为当前用户"""
    user_id = request.state.user_id
    account = request.state.account
    log.info("新建项目: user_id=%s team_id=%s name=%s", user_id, team_id, req.name)
    project = await service.create_project(
        team_id, user_id, account, req.name, req.description, req.owner_account,
    )
    return ResponseObject(data=project)


@api.get('/{team_id}/projects')
async def list_projects(team_id: int, request: Request):
    """团队项目列表（按自定义排序，含负责人昵称）"""
    projects = await service.list_projects(team_id, request.state.user_id)
    return ResponseObject(data=projects)


@api.delete('/{team_id}/delete')
async def delete_team(team_id: int, request: Request):
    """解散团队（仅团队所有者）：级联删除团队、项目、知识库、文件全部数据"""
    log.info("解散团队: user_id=%s team_id=%s", request.state.user_id, team_id)
    await service.delete_team(team_id, request.state.user_id)
    return ResponseObject(message='团队已解散')


@kb_api.get('/{kb_id}')
async def get_knowledge_base(kb_id: int, request: Request):
    """知识库详情（项目成员可查，含所属项目/团队ID）"""
    kb = await service.get_project_knowledge_base(kb_id, request.state.user_id)
    return ResponseObject(data=kb)


@kb_api.delete('/{kb_id}/delete')
async def delete_knowledge_base(kb_id: int, request: Request):
    """删除知识库（项目成员可删）：级联清理文件、策略、向量与解析任务"""
    log.info("删除知识库: user_id=%s kb_id=%s", request.state.user_id, kb_id)
    await service.delete_knowledge_base(kb_id, request.state.user_id)
    return ResponseObject(message='知识库已删除')


@project_api.get('/{project_id}')
async def get_project(project_id: int, request: Request):
    """项目详情（含负责人昵称与成员数）"""
    project = await service.get_project(project_id, request.state.user_id)
    return ResponseObject(data=project)


@project_api.delete('/{project_id}/delete')
async def delete_project(project_id: int, request: Request):
    """解散项目（仅项目负责人）：级联删除项目、知识库、文件全部数据"""
    log.info("解散项目: user_id=%s project_id=%s", request.state.user_id, project_id)
    await service.delete_project(project_id, request.state.user_id)
    return ResponseObject(message='项目已解散')


@project_api.get('/{project_id}/members')
async def list_project_members(
    project_id: int,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    query: str = Query(default='', max_length=64),
):
    """项目成员分页列表（负责人置顶，支持昵称/账号模糊搜索）"""
    result = await service.list_project_members(
        project_id, request.state.user_id, page, page_size, query,
    )
    return ResponseObject(data=result)


@project_api.get('/{project_id}/members/me')
async def my_project_membership(project_id: int, request: Request):
    """我在项目中的成员信息（非成员的团队成员首次进入时自动加入）"""
    member = await service.get_my_project_membership(
        project_id, request.state.user_id, request.state.account,
    )
    return ResponseObject(data=member)


@project_api.post('/{project_id}/members/add')
async def add_project_member(project_id: int, req: AddMemberRequest, request: Request):
    """添加项目成员（项目成员可添加，目标须为团队成员）"""
    log.info("添加项目成员: user_id=%s project_id=%s account=%s",
             request.state.user_id, project_id, req.account)
    member = await service.add_project_member(project_id, request.state.user_id, req.account)
    return ResponseObject(data=member)


@project_api.get('/{project_id}/knowledge-bases')
async def list_project_knowledge_bases(project_id: int, request: Request):
    """项目知识库列表（按自定义排序）"""
    kbs = await service.list_project_knowledge_bases(project_id, request.state.user_id)
    return ResponseObject(data=kbs)


@project_api.post('/{project_id}/knowledge-bases/create')
async def create_project_knowledge_base(
    project_id: int, req: CreateProjectKnowledgeBaseRequest, request: Request,
):
    """新建项目知识库（知识库名项目内唯一）"""
    log.info("新建项目知识库: user_id=%s project_id=%s name=%s",
             request.state.user_id, project_id, req.name)
    kb = await service.create_project_knowledge_base(
        project_id, request.state.user_id, req.name, req.description, req.embed_model,
    )
    return ResponseObject(data=kb)
