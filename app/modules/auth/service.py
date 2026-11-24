"""认证域业务逻辑：注册、登录、续期、退出、改密与鉴权校验

职责划分（设计方案 §1.2）：
- 改密走 token_version（全端失效），退出走 JTI 黑名单（精确撤销）；
- AT短效无状态只做业务鉴权，RT长效有状态只做续期，一次一用；
- RT重用即判定令牌泄露：撤销整个轮换族并告警。
"""

import logging
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import jwt

from config.settings import settings
from core.exceptions import BusinessError
from modules.auth import repository, security
from modules.auth.constants import (
    CODE_ACCOUNT_LOCKED,
    CODE_REFRESH_TOKEN_INVALID,
    CODE_SESSION_REVOKED,
    CODE_TOKEN_REVOKED,
    CODE_TOKEN_VERSION_MISMATCH,
    CODE_USER_DISABLED,
)
from modules.auth.schema import TokenBundle, UserInfo
from modules.auth.store import (
    auth_store,
    blacklist_key,
    family_key,
    grace_key,
    login_fail_key,
    login_lock_key,
    rt_key,
    session_key,
    user_sessions_key,
    user_tv_key,
)

log = logging.getLogger(__name__)

# 存储 TTL（秒）
_TV_CACHE_TTL = settings.USER_STATE_CACHE_TTL  # 用户版本号/状态缓存，改密/禁用时主动失效
_USER_INDEX_TTL = settings.RT_MAX_LIFETIME


@dataclass
class AuthContext:
    """拦截器校验通过后注入请求上下文的身份信息"""
    user_id: int
    account: str
    sid: str
    jti: str
    exp: int
    token_version: int


# ---------------- 内部：令牌签发与存储写入 ----------------
def _now() -> int:
    return int(time.time())


async def _cache_user_state(user_id: int, token_version: int, status: int) -> None:
    """版本号+状态合并缓存，拦截器避免每请求查库（设计方案 §7 性能说明）"""
    await auth_store.set_json(user_tv_key(user_id), {'token_version': token_version, 'status': status}, _TV_CACHE_TTL)


async def _revoke_family(family_id: str, revoke_session_sid: Optional[str] = None) -> None:
    """撤销轮换族下全部RT；指定sid时连会话一并撤销（重用检测/退出场景）"""
    for token_hash in await auth_store.get_set(family_key(family_id)):
        await auth_store.delete(rt_key(token_hash))
    await auth_store.delete_set(family_key(family_id))
    if revoke_session_sid:
        await auth_store.delete(session_key(revoke_session_sid))
    await repository.audit_revoke_by_family(family_id)


async def _issue_bundle(
        user: dict,
        sid: str,
        family_id: str,
        family_expires_at: int,
        device: Optional[str],
        ip: Optional[str],
        new_session: bool,
) -> TokenBundle:
    """为既有会话签发AT+RT并写入存储（登录建会话 / 续期轮换复用）"""
    user_id = int(user['id'])
    token_version = user['token_version']
    now = _now()

    if new_session:
        await auth_store.set_json(session_key(sid), {
            'user_id': user_id,
            'account': user['account'],
            'status': 'active',
            'device': device or '',
            'ip': ip or '',
            'family_id': family_id,
            'created_at': now,
            'last_refresh_at': now,
        }, settings.RT_MAX_LIFETIME)
        await auth_store.add_to_set(user_sessions_key(user_id), sid, _USER_INDEX_TTL)
    else:
        session = await auth_store.get_json(session_key(sid))
        if session:
            session['last_refresh_at'] = now
            await auth_store.set_json(session_key(sid), session, settings.RT_MAX_LIFETIME)

    at = security.create_access_token(user_id, sid, token_version)

    # RT剩余有效期 = min(滑动窗口, 族绝对寿命)（设计方案 §4.2）
    rt_expires_at = min(now + settings.RT_SLIDING_TTL, family_expires_at)
    if rt_expires_at <= now:
        raise BusinessError('登录已过期，请重新登录', code=CODE_REFRESH_TOKEN_INVALID)
    rt = security.create_refresh_token()
    token_hash = security.hash_refresh_token(rt)
    await auth_store.set_json(rt_key(token_hash), {
        'user_id': user_id,
        'sid': sid,
        'family_id': family_id,
        'token_version': token_version,
        'status': 1,
        'expires_at': rt_expires_at,
        'family_expires_at': family_expires_at,
    }, rt_expires_at - now)
    await auth_store.add_to_set(family_key(family_id), token_hash, family_expires_at - now)

    await _cache_user_state(user_id, token_version, int(user.get('status', 1)))
    await repository.audit_insert_rt(token_hash, user_id, sid, family_id, rt_expires_at)

    return TokenBundle(
        access_token=at,
        expires_in=settings.AT_TTL,
        refresh_token=rt,
        user=UserInfo(id=str(user_id), account=user['account'], created_at=user.get('created_at')),
    )


# ---------------- 注册 ----------------
async def register(account: str, password: str) -> dict:
    account = account.strip()
    if await repository.get_user_by_account(account):
        raise BusinessError('该账号已被注册，请直接登录', code=40002, status_code=400)
    return await repository.create_user(account, security.hash_password(password))


# ---------------- 登录防暴力破解 ----------------
async def _ensure_not_locked(account: str) -> None:
    """锁定中的账号直接拒绝登录（含剩余时间提示）；锁到期自然恢复"""
    expiry_raw = await auth_store.get_string(login_lock_key(account))
    if expiry_raw is None:
        return
    remaining = int(expiry_raw) - _now()
    if remaining <= 0:
        await auth_store.delete(login_lock_key(account))
        return
    minutes = max(1, -(-remaining // 60))  # 向上取整
    raise BusinessError(f'登录失败次数过多，账号已锁定，请约{minutes}分钟后重试',
                    code=CODE_ACCOUNT_LOCKED, status_code=429)


async def _record_login_failure(account: str) -> None:
    """连续失败计数（计数窗口=锁定时长）；达到阈值即锁定并清零计数"""
    fails = await auth_store.incr_with_ttl(login_fail_key(account), settings.LOGIN_LOCK_TTL)
    if fails >= settings.LOGIN_MAX_FAILS:
        await auth_store.delete(login_fail_key(account))
        await auth_store.set_string(login_lock_key(account), str(_now() + settings.LOGIN_LOCK_TTL),
                                    settings.LOGIN_LOCK_TTL)
        log.warning("账号连续登录失败%d次，锁定%d秒 account=%s", fails, settings.LOGIN_LOCK_TTL, account)


async def _clear_login_failures(account: str) -> None:
    """登录成功即清零连续失败计数"""
    await auth_store.delete(login_fail_key(account))


# ---------------- 登录 ----------------
async def login(account: str, password: str, device_id: Optional[str], ip: Optional[str]) -> TokenBundle:
    account = account.strip()
    # 防暴力破解：锁定中先拒绝（对存在/不存在的账号行为一致，防枚举）
    await _ensure_not_locked(account)
    # 失败统一返回"账号或密码错误"，不区分账号不存在/密码错误（防枚举）
    user = await repository.verify_password_hash(account, password)
    if not user:
        await _record_login_failure(account)
        raise BusinessError('账号或密码错误', code=40003, status_code=400)
    await _clear_login_failures(account)
    if user.get('status', 1) != 1:
        raise BusinessError('账号已被禁用', code=CODE_USER_DISABLED, status_code=403)
    sid = f'sess_{secrets.token_hex(8)}'
    family_id = uuid.uuid4().hex
    return await _issue_bundle(user, sid, family_id, _now() + settings.RT_MAX_LIFETIME, device_id, ip, new_session=True)


# ---------------- 续期（RT一次一用 + 重用检测，设计方案 §6.2） ----------------
async def refresh(refresh_token: Optional[str], ip: Optional[str]) -> TokenBundle:
    if not refresh_token:
        raise BusinessError('缺少Refresh Token', code=CODE_REFRESH_TOKEN_INVALID)
    now = _now()
    token_hash = security.hash_refresh_token(refresh_token)
    record, reused = await auth_store.consume_rt(rt_key(token_hash), now)

    if record is None:
        raise BusinessError('Refresh Token无效', code=CODE_REFRESH_TOKEN_INVALID)

    if reused:
        # 宽限窗口（默认关闭）：网络重试导致窗口内二次使用 → 返回同一新RT（设计方案 §11）
        if settings.RT_GRACE > 0:
            grace_rt = await auth_store.get_string(grace_key(token_hash))
            if grace_rt:
                return await _reissue_at_for_grace(record, grace_rt, ip)
        # 重用检测：同族RT再次出现即判定泄露 → 撤销全族+会话并告警
        log.warning("检测到Refresh Token重用，撤销整个轮换族 family_id=%s ip=%s", record.get('family_id'), ip)
        await _revoke_family(record['family_id'], revoke_session_sid=record['sid'])
        raise BusinessError('Refresh Token已失效，请重新登录', code=CODE_REFRESH_TOKEN_INVALID)

    if record['expires_at'] <= now:
        await auth_store.delete(rt_key(token_hash))
        raise BusinessError('Refresh Token已过期，请重新登录', code=CODE_REFRESH_TOKEN_INVALID)

    # 会话须存在且active
    session = await auth_store.get_json(session_key(record['sid']))
    if not session or session.get('status') != 'active':
        raise BusinessError('会话已失效，请重新登录', code=CODE_SESSION_REVOKED)

    # 用户须正常且版本号一致（改密后旧RT在此被拒）
    tv_cache = await auth_store.get_json(user_tv_key(record['user_id']))
    if tv_cache is None:
        db_user = await repository.get_user_by_id(record['user_id'])
        if not db_user:
            raise BusinessError('会话已失效，请重新登录', code=CODE_SESSION_REVOKED)
        tv_cache = {'token_version': db_user['token_version'], 'status': db_user['status']}
    if tv_cache['status'] != 1:
        raise BusinessError('账号已被禁用', code=CODE_USER_DISABLED, status_code=403)
    if tv_cache['token_version'] != record['token_version']:
        raise BusinessError('令牌版本已更新，请重新登录', code=CODE_TOKEN_VERSION_MISMATCH)

    user = {'id': record['user_id'], 'account': session.get('account') or '',
            'token_version': record['token_version'], 'status': tv_cache['status']}
    new_rt = await _issue_bundle(user, record['sid'], record['family_id'],
                                 record['family_expires_at'], session.get('device'), ip, new_session=False)
    await repository.audit_mark_used(token_hash, security.hash_refresh_token(new_rt.refresh_token), now)
    if settings.RT_GRACE > 0:
        await auth_store.set_string(grace_key(token_hash), new_rt.refresh_token, settings.RT_GRACE)
    # 旧RT哈希移出族索引，避免索引无限膨胀
    await auth_store.remove_from_set(family_key(record['family_id']), token_hash)
    return new_rt


async def _reissue_at_for_grace(record: dict, rt: str, ip: Optional[str]) -> TokenBundle:
    """宽限窗口内重放：不轮换RT，直接返回同一新RT并重签AT"""
    tv_cache = await auth_store.get_json(user_tv_key(record['user_id']))
    user = await repository.get_user_by_id(record['user_id'])
    token_version = (tv_cache or {}).get('token_version') or (user or {}).get('token_version')
    if not user or user.get('status', 1) != 1 or token_version != record['token_version']:
        raise BusinessError('Refresh Token已失效，请重新登录', code=CODE_REFRESH_TOKEN_INVALID)
    return TokenBundle(
        access_token=security.create_access_token(record['user_id'], record['sid'], token_version),
        expires_in=settings.AT_TTL,
        refresh_token=rt,
        user=UserInfo(id=str(user['id']), account=user['account'], created_at=user.get('created_at')),
    )


# ---------------- 退出（幂等：重复退出也返回成功） ----------------
async def logout(access_token: Optional[str]) -> None:
    if not access_token:
        return
    try:
        # 退出允许携带已过期AT（签名有效即可定位会话），故关闭exp校验
        payload = jwt.decode(access_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM],
                             options={'verify_exp': False})
    except jwt.PyJWTError:
        return
    jti, sid = payload.get('jti'), payload.get('sid')
    exp = int(payload.get('exp', 0))
    now = _now()
    # 黑名单TTL = AT剩余有效期（关键：自动清理，禁止设固定大TTL）
    if jti and exp > now:
        await auth_store.set_string(blacklist_key(jti), '1', exp - now)
    session = await auth_store.get_json(session_key(sid)) if sid else None
    if session:
        await auth_store.delete(session_key(sid))
        await auth_store.remove_from_set(user_sessions_key(int(session['user_id'])), sid)
        await _revoke_family(session.get('family_id', ''))
    log.info("用户退出登录 sid=%s", sid)


# ---------------- 修改密码（版本号全端失效，设计方案 §6.4） ----------------
async def change_password(user_id: int, old_password: str, new_password: str, ip: Optional[str]) -> TokenBundle:
    creds = await repository.get_credentials(user_id)
    if not creds or not security.verify_password(old_password, creds['password_hash']):
        raise BusinessError('原密码错误', code=40001, status_code=400)

    new_version = await repository.update_password_and_bump_version(user_id, security.hash_password(new_password))

    # 清版本号缓存：避免缓存不一致延长旧Token存活（设计方案 §10）
    await auth_store.delete(user_tv_key(user_id))

    # 撤销该用户全部会话与RT（清理存储；审计表同步标记）
    for sid in await auth_store.get_set(user_sessions_key(user_id)):
        session = await auth_store.get_json(session_key(sid))
        if session:
            await _revoke_family(session.get('family_id', ''))
        await auth_store.delete(session_key(sid))
    await auth_store.delete_set(user_sessions_key(user_id))
    await repository.audit_revoke_by_user(user_id)

    # 当前设备重新签发一套AT/RT，避免用户立刻被登出（推荐体验）
    user = {'id': user_id, 'account': creds['account'], 'token_version': new_version, 'status': 1}
    sid = f'sess_{secrets.token_hex(8)}'
    family_id = uuid.uuid4().hex
    return await _issue_bundle(user, sid, family_id, _now() + settings.RT_MAX_LIFETIME, None, ip, new_session=True)


# ---------------- 统一鉴权校验（设计方案 §7，顺序不可调换） ----------------
async def search_accounts(query: str) -> list[dict]:
    """搜索系统账号（添加成员选人用，仅返回正常状态账号）"""
    return await repository.search_users((query or '').strip())


async def authenticate(token: str) -> AuthContext:
    payload = security.decode_access_token(token)  # 1~2步：验签+exp（40101/40102）
    user_id = int(payload['sub'])
    jti, sid = payload.get('jti', ''), payload.get('sid', '')
    now = _now()

    # 3. jti黑名单（40103）
    if await auth_store.get_string(blacklist_key(jti)) is not None:
        raise BusinessError('令牌已撤销，请重新登录', code=CODE_TOKEN_REVOKED)

    # 4. 会话状态（40104）
    session = await auth_store.get_json(session_key(sid))
    if not session or session.get('status') != 'active':
        raise BusinessError('会话已失效，请重新登录', code=CODE_SESSION_REVOKED)

    # 5. token_version比对：优先缓存，miss查库回填（40105）
    tv_cache = await auth_store.get_json(user_tv_key(user_id))
    if tv_cache is None:
        db_user = await repository.get_user_by_id(user_id)
        if not db_user:
            raise BusinessError('会话已失效，请重新登录', code=CODE_SESSION_REVOKED)
        tv_cache = {'token_version': db_user['token_version'], 'status': db_user['status']}
        await _cache_user_state(user_id, tv_cache['token_version'], tv_cache['status'])
    if tv_cache['token_version'] != payload.get('token_version'):
        raise BusinessError('令牌版本已更新，请重新登录', code=CODE_TOKEN_VERSION_MISMATCH)

    # 6. 用户status（40301）
    if tv_cache['status'] != 1:
        raise BusinessError('账号已被禁用', code=CODE_USER_DISABLED, status_code=403)

    return AuthContext(user_id=user_id, account=session.get('account') or '', sid=sid,
                       jti=jti, exp=int(payload['exp']), token_version=int(payload.get('token_version', 0)))
