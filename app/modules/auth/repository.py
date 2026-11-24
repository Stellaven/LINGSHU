"""认证域数据访问层：用户表读写 + Refresh Token审计表

审计表为辅助数据（主数据在store层），写入失败仅记日志，不影响鉴权主流程。
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update

from core.dependencies import get_db_session
from db.pg.orm_models import AuthRefreshToken, User

log = logging.getLogger(__name__)


def _to_epoch(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _user_to_dict(user: User) -> dict:
    """脱敏输出：不携带密码哈希"""
    return {
        'id': str(user.id),
        'account': user.account,
        'token_version': user.token_version,
        'status': user.status,
        'created_at': user.created_at.isoformat() if user.created_at else None,
    }


async def get_user_by_account(account: str) -> Optional[dict]:
    async with get_db_session() as session:
        user = (await session.execute(select(User).where(User.account == account))).scalar_one_or_none()
        return _user_to_dict(user) if user else None


async def get_user_by_id(user_id: int) -> Optional[dict]:
    async with get_db_session() as session:
        user = await session.get(User, user_id)
        return _user_to_dict(user) if user else None


async def search_users(query: str, limit: int = 20) -> list[dict]:
    """按账号前缀/包含模糊搜索正常状态用户（添加成员选人用），按账号排序"""
    async with get_db_session() as session:
        stmt = select(User).where(User.status == 1)
        if query:
            stmt = stmt.where(User.account.ilike(f'%{query}%'))
        rows = (await session.execute(
            stmt.order_by(User.account).limit(limit)
        )).scalars().all()
        return [{'id': str(u.id), 'account': u.account} for u in rows]


async def create_user(account: str, password_hash: str) -> dict:
    async with get_db_session() as session:
        user = User(account=account, password_hash=password_hash)
        session.add(user)
        await session.flush()
        data = _user_to_dict(user)
        return data


async def get_credentials(user_id: int) -> Optional[dict]:
    """改密场景：读取密码哈希与账号（含敏感字段，不对外输出）"""
    async with get_db_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return None
        return {'account': user.account, 'password_hash': user.password_hash,
                'token_version': user.token_version, 'status': user.status}


async def verify_password_hash(account: str, password: str) -> Optional[dict]:
    """登录校验：取哈希比对（哈希不脱敏外传）。失败返回None，调用方统一返回"账号或密码错误" """
    from modules.auth.security import verify_password

    async with get_db_session() as session:
        user = (await session.execute(select(User).where(User.account == account))).scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            return None
        return _user_to_dict(user)


async def update_password_and_bump_version(user_id: int, password_hash: str) -> int:
    """单条UPDATE原子完成改密+版本号自增（设计方案 §6.4），返回新版本号"""
    async with get_db_session() as session:
        result = await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(password_hash=password_hash, token_version=User.token_version + 1)
            .returning(User.token_version)
        )
        return result.scalar_one()


# ---------------- RT审计表（best-effort） ----------------
async def audit_insert_rt(token_hash: str, user_id: int, sid: str, family_id: str, expires_at_ts: int) -> None:
    try:
        async with get_db_session() as session:
            session.add(AuthRefreshToken(
                token_hash=token_hash,
                user_id=user_id,
                sid=sid,
                family_id=family_id,
                status=1,
                expires_at=datetime.fromtimestamp(expires_at_ts, tz=timezone.utc),
            ))
    except Exception:
        log.warning("RT审计记录写入失败 token_hash=%s", token_hash[:8], exc_info=True)


async def audit_mark_used(token_hash: str, replaced_by: str, used_at_ts: int) -> None:
    try:
        async with get_db_session() as session:
            await session.execute(
                update(AuthRefreshToken)
                .where(AuthRefreshToken.token_hash == token_hash)
                .values(status=2, replaced_by=replaced_by,
                        used_at=datetime.fromtimestamp(used_at_ts, tz=timezone.utc))
            )
    except Exception:
        log.warning("RT审计状态更新失败 token_hash=%s", token_hash[:8], exc_info=True)


async def audit_revoke_by_family(family_id: str) -> None:
    try:
        async with get_db_session() as session:
            await session.execute(
                update(AuthRefreshToken)
                .where(AuthRefreshToken.family_id == family_id, AuthRefreshToken.status == 1)
                .values(status=3)
            )
    except Exception:
        log.warning("RT审计按族撤销失败 family_id=%s", family_id, exc_info=True)


async def audit_revoke_by_user(user_id: int) -> None:
    try:
        async with get_db_session() as session:
            await session.execute(
                update(AuthRefreshToken)
                .where(AuthRefreshToken.user_id == user_id, AuthRefreshToken.status == 1)
                .values(status=3)
            )
    except Exception:
        log.warning("RT审计按用户撤销失败 user_id=%s", user_id, exc_info=True)
