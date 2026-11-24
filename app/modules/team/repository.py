"""团队域数据访问层：团队/成员/项目/项目成员四表读写

出参统一序列化为前端契约（camelCase + 字符串id），见 web/src/types/team.ts。
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, func, select

from core.dependencies import get_db_session
from db.pg.orm_models import (
    ProjectKnowledgeBase,
    ProjectMember,
    Team,
    TeamMember,
    TeamProject,
    User,
)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _team_to_dict(team: Team, my_role: Optional[str] = None) -> dict:
    data = {
        'id': str(team.id),
        'name': team.name,
        'description': team.description or '',
        'createdAt': _iso(team.created_at),
    }
    if my_role is not None:
        data['myRole'] = my_role
    return data


def _member_to_dict(member: TeamMember) -> dict:
    return {
        'id': str(member.id),
        'teamId': str(member.team_id),
        'userId': str(member.user_id),
        'account': member.account,
        'nickname': member.nickname,
        # users表无邮箱字段，暂返回空串，前端展示回退账号
        'email': '',
        'role': member.role,
        'joinedAt': _iso(member.joined_at),
    }


def _project_to_dict(project: TeamProject, owner_account: str, owner_name: str,
                     member_count: int) -> dict:
    return {
        'id': str(project.id),
        'teamId': str(project.team_id),
        'name': project.name,
        'description': project.description or '',
        'ownerAccount': owner_account,
        'memberCount': member_count,
        'createdAt': _iso(project.created_at),
        'sortOrder': project.sort_order,
        'ownerName': owner_name,
    }


async def create_team(creator_user_id: int, creator_account: str, name: str, description: str) -> dict:
    """建团 + 创建者写入所有者成员记录（同事务）"""
    async with get_db_session() as session:
        team = Team(name=name, description=description, created_by=creator_user_id)
        session.add(team)
        await session.flush()
        session.add(TeamMember(
            team_id=team.id, user_id=creator_user_id,
            account=creator_account, nickname=creator_account, role='owner',
        ))
        await session.refresh(team)
        return _team_to_dict(team)


async def list_teams_for_user(user_id: int) -> list[dict]:
    """我参与的团队（含我的角色），按入团先后排序"""
    async with get_db_session() as session:
        rows = (await session.execute(
            select(Team, TeamMember.role)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == user_id)
            .order_by(TeamMember.joined_at, Team.id)
        )).all()
        return [_team_to_dict(team, my_role=role) for team, role in rows]


async def get_team(team_id: int) -> Optional[dict]:
    async with get_db_session() as session:
        team = await session.get(Team, team_id)
        return _team_to_dict(team) if team else None


async def get_member_by_user(team_id: int, user_id: int) -> Optional[dict]:
    async with get_db_session() as session:
        member = (await session.execute(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        )).scalar_one_or_none()
        return _member_to_dict(member) if member else None


async def get_member_by_account(team_id: int, account: str) -> Optional[dict]:
    async with get_db_session() as session:
        member = (await session.execute(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.account == account)
        )).scalar_one_or_none()
        return _member_to_dict(member) if member else None


async def get_system_user_by_account(account: str) -> Optional[dict]:
    """按账号查询系统用户（正常状态），仅返回 id/account"""
    async with get_db_session() as session:
        user = (await session.execute(
            select(User).where(User.account == account, User.status == 1)
        )).scalar_one_or_none()
        return {'id': str(user.id), 'account': user.account} if user else None


async def add_member(team_id: int, user_id: int, account: str, nickname: str = '') -> dict:
    """添加团队成员（角色为 member，昵称缺省取账号）"""
    async with get_db_session() as session:
        member = TeamMember(
            team_id=team_id, user_id=user_id,
            account=account, nickname=nickname or account, role='member',
        )
        session.add(member)
        await session.flush()
        await session.refresh(member)
        return _member_to_dict(member)


async def list_members(team_id: int, page: int, page_size: int, query: str = '') -> dict:
    """成员分页列表：所有者置顶，其余按入团时间；支持昵称/账号模糊搜索"""
    async with get_db_session() as session:
        stmt = select(TeamMember).where(TeamMember.team_id == team_id)
        if query:
            kw = f'%{query}%'
            stmt = stmt.where(TeamMember.nickname.ilike(kw) | TeamMember.account.ilike(kw))
        total = (await session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        rows = (await session.execute(
            stmt.order_by(TeamMember.role.desc(), TeamMember.joined_at, TeamMember.id)
            .offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        return {
            'items': [_member_to_dict(m) for m in rows],
            'total': total,
            'page': page,
            'pageSize': page_size,
        }


async def create_project(team_id: int, name: str, description: str,
                         owner_member: dict, creator_user_id: int, creator_account: str) -> dict:
    """建项目 + 负责人（及创建人非同一人时的创建人）写入项目成员记录（同事务）"""
    async with get_db_session() as session:
        max_sort = (await session.execute(
            select(func.max(TeamProject.sort_order)).where(TeamProject.team_id == team_id)
        )).scalar() or 0
        owner_user_id = int(owner_member['userId'])
        project = TeamProject(
            team_id=team_id, name=name, description=description,
            owner_user_id=owner_user_id,
            sort_order=max_sort + 1,
        )
        session.add(project)
        await session.flush()
        session.add(ProjectMember(
            project_id=project.id, user_id=owner_user_id, account=owner_member['account'],
            nickname=owner_member['nickname'], role='owner',
        ))
        if creator_user_id != owner_user_id:
            session.add(ProjectMember(
                project_id=project.id, user_id=creator_user_id, account=creator_account,
                nickname=creator_account, role='member',
            ))
        await session.refresh(project)
        return _project_to_dict(project, owner_account=owner_member['account'],
                                owner_name=owner_member['nickname'],
                                member_count=2 if creator_user_id != owner_user_id else 1)


async def list_projects(team_id: int) -> list[dict]:
    """项目列表：按自定义排序值，附带负责人昵称与成员数"""
    async with get_db_session() as session:
        rows = (await session.execute(
            select(TeamProject, TeamMember.account, TeamMember.nickname)
            .join(TeamMember, (TeamMember.team_id == TeamProject.team_id)
                  & (TeamMember.user_id == TeamProject.owner_user_id))
            .where(TeamProject.team_id == team_id)
            .order_by(TeamProject.sort_order, TeamProject.id)
        )).all()
        if not rows:
            return []
        counts = dict((await session.execute(
            select(ProjectMember.project_id, func.count())
            .where(ProjectMember.project_id.in_([p.id for p, _, _ in rows]))
            .group_by(ProjectMember.project_id)
        )).all())
        return [_project_to_dict(p, owner_account=account, owner_name=nickname,
                                 member_count=counts.get(p.id, 0))
                for p, account, nickname in rows]


def _project_member_to_dict(member: ProjectMember) -> dict:
    return {
        'id': str(member.id),
        'projectId': str(member.project_id),
        'userId': str(member.user_id),
        'account': member.account,
        'nickname': member.nickname,
        # users表无邮箱字段，暂返回空串，前端展示回退账号
        'email': '',
        'role': member.role,
        'joinedAt': _iso(member.joined_at),
    }


async def list_project_members(project_id: int, page: int, page_size: int,
                               query: str = '') -> dict:
    """项目成员分页列表：负责人置顶，其余按加入时间；支持昵称/账号模糊搜索"""
    async with get_db_session() as session:
        stmt = select(ProjectMember).where(ProjectMember.project_id == project_id)
        if query:
            kw = f'%{query}%'
            stmt = stmt.where(ProjectMember.nickname.ilike(kw) | ProjectMember.account.ilike(kw))
        total = (await session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        rows = (await session.execute(
            stmt.order_by(ProjectMember.role.desc(), ProjectMember.joined_at, ProjectMember.id)
            .offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        return {
            'items': [_project_member_to_dict(m) for m in rows],
            'total': total,
            'page': page,
            'pageSize': page_size,
        }


async def get_project(project_id: int) -> Optional[dict]:
    """项目详情：附带负责人昵称与成员数"""
    async with get_db_session() as session:
        row = (await session.execute(
            select(TeamProject, TeamMember.account, TeamMember.nickname)
            .join(TeamMember, (TeamMember.team_id == TeamProject.team_id)
                  & (TeamMember.user_id == TeamProject.owner_user_id))
            .where(TeamProject.id == project_id)
        )).first()
        if not row:
            return None
        project, account, nickname = row
        member_count = (await session.execute(
            select(func.count()).select_from(ProjectMember)
            .where(ProjectMember.project_id == project_id)
        )).scalar_one()
        return _project_to_dict(project, owner_account=account, owner_name=nickname,
                                member_count=member_count)


def _project_kb_to_dict(kb: ProjectKnowledgeBase) -> dict:
    return {
        'id': str(kb.id),
        'name': kb.name,
        'description': kb.description or '',
        'projectId': str(kb.project_id),
        # 向量模型
        'embedModel': kb.embed_model,
        # TODO(backend): 文件/分块统计随文档模块接入后返回
        'fileCount': 0,
        'chunkCount': 0,
        'createdAt': _iso(kb.created_at),
        'updatedAt': _iso(kb.updated_at),
        'sortOrder': kb.sort_order,
    }


async def project_exists(project_id: int) -> bool:
    async with get_db_session() as session:
        return await session.get(TeamProject, project_id) is not None


async def is_project_member(project_id: int, user_id: int) -> bool:
    async with get_db_session() as session:
        return (await session.execute(
            select(ProjectMember.id).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        )).scalar_one_or_none() is not None


async def get_project_member_by_user(project_id: int, user_id: int) -> Optional[dict]:
    async with get_db_session() as session:
        member = (await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        )).scalar_one_or_none()
        return _project_member_to_dict(member) if member else None


async def join_project(project_id: int, user_id: int, account: str) -> dict:
    """以项目成员身份加入项目（团队成员首次进入项目时自动加入，与mock语义一致）"""
    async with get_db_session() as session:
        member = ProjectMember(
            project_id=project_id, user_id=user_id,
            account=account, nickname=account, role='member',
        )
        session.add(member)
        await session.flush()
        await session.refresh(member)
        return _project_member_to_dict(member)


async def add_project_member(project_id: int, user_id: int, account: str, nickname: str = '') -> dict:
    """添加项目成员（角色为 member，昵称缺省取账号）"""
    async with get_db_session() as session:
        member = ProjectMember(
            project_id=project_id, user_id=user_id,
            account=account, nickname=nickname or account, role='member',
        )
        session.add(member)
        await session.flush()
        await session.refresh(member)
        return _project_member_to_dict(member)


async def get_project_knowledge_base(kb_id: int) -> Optional[dict]:
    """知识库详情（附带所属团队ID）"""
    async with get_db_session() as session:
        row = (await session.execute(
            select(ProjectKnowledgeBase, TeamProject.team_id)
            .join(TeamProject, TeamProject.id == ProjectKnowledgeBase.project_id)
            .where(ProjectKnowledgeBase.id == kb_id)
        )).first()
        if not row:
            return None
        kb, team_id = row
        data = _project_kb_to_dict(kb)
        data['teamId'] = str(team_id)
        return data


async def list_project_knowledge_bases(project_id: int) -> list[dict]:
    """项目知识库列表：按自定义排序值"""
    async with get_db_session() as session:
        kbs = (await session.execute(
            select(ProjectKnowledgeBase)
            .where(ProjectKnowledgeBase.project_id == project_id)
            .order_by(ProjectKnowledgeBase.sort_order, ProjectKnowledgeBase.id)
        )).scalars().all()
        return [_project_kb_to_dict(kb) for kb in kbs]


async def project_kb_name_exists(project_id: int, name: str) -> bool:
    async with get_db_session() as session:
        return (await session.execute(
            select(ProjectKnowledgeBase.id).where(
                ProjectKnowledgeBase.project_id == project_id,
                ProjectKnowledgeBase.name == name)
        )).scalar_one_or_none() is not None


async def create_project_knowledge_base(
    project_id: int, name: str, description: str, embed_model: str = 'bge-m3',
) -> dict:
    """新建项目知识库，排序值取项目内当前最大值+1"""
    async with get_db_session() as session:
        max_sort = (await session.execute(
            select(func.max(ProjectKnowledgeBase.sort_order))
            .where(ProjectKnowledgeBase.project_id == project_id)
        )).scalar() or 0
        kb = ProjectKnowledgeBase(
            project_id=project_id, name=name, description=description,
            embed_model=embed_model, sort_order=max_sort + 1,
        )
        session.add(kb)
        await session.flush()
        await session.refresh(kb)
        return _project_kb_to_dict(kb)


# ---------------- 级联删除（解散团队/项目、删除知识库） ----------------

async def delete_team(team_id: int) -> None:
    """删除团队及其成员关系记录（项目等子数据由service级联清理后再调用）"""
    async with get_db_session() as session:
        await session.execute(delete(TeamMember).where(TeamMember.team_id == team_id))
        await session.execute(delete(Team).where(Team.id == team_id))
        await session.commit()


async def delete_project(project_id: int) -> None:
    """删除项目及其成员关系记录（项目下知识库等子数据由service级联清理后再调用）"""
    async with get_db_session() as session:
        await session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
        await session.execute(delete(TeamProject).where(TeamProject.id == project_id))
        await session.commit()


async def delete_knowledge_base(kb_id: int) -> None:
    """删除知识库记录（文件/策略/向量/任务等子数据由service级联清理后再调用）"""
    async with get_db_session() as session:
        await session.execute(delete(ProjectKnowledgeBase).where(ProjectKnowledgeBase.id == kb_id))
        await session.commit()
