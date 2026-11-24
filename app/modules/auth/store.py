"""认证态存储层：会话、RT记录、JTI黑名单、版本号缓存的统一读写

技术设计方案 §5.2：主数据放Redis；本环境可能无Redis（REDIS_URL留空），
降级为进程内存TTL存储，接口语义与Redis一致，仅限本地开发/单实例部署。

原子性说明：
- RT"一次一用"的标记必须原子（设计方案 §10）。Redis侧用Lua脚本完成
  「查状态→标记used」；内存侧依赖单事件循环内无await的同步段天然原子。
"""

import json
import time
from typing import Any, Optional

import redis.asyncio as aioredis

from config.settings import settings
from modules.auth.constants import (
    KEY_BLACKLIST,
    KEY_FAMILY,
    KEY_GRACE,
    KEY_LOGIN_FAIL,
    KEY_LOGIN_LOCK,
    KEY_RT,
    KEY_SESSION,
    KEY_USER_SESSIONS,
    KEY_USER_TV,
)

# consume_rt 返回标记（跨Redis Lua与内存实现统一）
_RT_OK = '__ok__'
_RT_USED = '__used__'
_RT_MISSING = '__missing__'


class MemoryStore:
    """进程内存TTL存储（Redis降级实现）：key → (value, expires_at)"""

    def __init__(self):
        self._kv: dict[str, tuple[Any, float]] = {}
        self._sets: dict[str, tuple[set[str], float]] = {}

    @staticmethod
    def _alive(expires_at: float) -> bool:
        return expires_at > time.time()

    async def get_json(self, key: str) -> Optional[dict]:
        item = self._kv.get(key)
        if item and self._alive(item[1]):
            return item[0]
        self._kv.pop(key, None)
        return None

    async def set_json(self, key: str, data: dict, ttl: int) -> None:
        self._kv[key] = (data, time.time() + ttl)

    async def delete(self, key: str) -> None:
        self._kv.pop(key, None)

    async def exists(self, key: str) -> bool:
        return await self.get_json(key) is not None

    async def add_to_set(self, key: str, member: str, ttl: int) -> None:
        members, expires_at = self._sets.get(key, (set(), time.time() + ttl))
        members.add(member)
        self._sets[key] = (members, max(expires_at, time.time() + ttl))

    async def remove_from_set(self, key: str, member: str) -> None:
        item = self._sets.get(key)
        if item:
            item[0].discard(member)

    async def get_set(self, key: str) -> list[str]:
        item = self._sets.get(key)
        if item and self._alive(item[1]):
            return list(item[0])
        self._sets.pop(key, None)
        return []

    async def delete_set(self, key: str) -> None:
        self._sets.pop(key, None)

    async def get_string(self, key: str) -> Optional[str]:
        item = self._kv.get(key)
        if item and self._alive(item[1]):
            return item[0]
        self._kv.pop(key, None)
        return None

    async def set_string(self, key: str, value: str, ttl: int) -> None:
        self._kv[key] = (value, time.time() + ttl)

    async def incr_with_ttl(self, key: str, ttl: int) -> int:
        """原子自增并保证TTL。无await的同步段：单事件循环内天然原子（同consume_rt约定）"""
        item = self._kv.get(key)
        if item and self._alive(item[1]):
            count = int(item[0]) + 1
            self._kv[key] = (str(count), item[1])  # 保留原过期时间
        else:
            count = 1
            self._kv[key] = ('1', time.time() + ttl)
        return count

    async def consume_rt(self, key: str, now_ts: int) -> tuple[Optional[dict], bool]:
        """原子标记RT为used。返回(记录, 是否已被使用过)"""
        item = self._kv.get(key)
        if not item or not self._alive(item[1]):
            self._kv.pop(key, None)
            return None, False
        record = item[0]
        if record.get('status') != 1:
            return record, True
        record['status'] = 2
        record['used_at'] = now_ts
        return record, False

    async def close(self) -> None:
        pass


class RedisStore:
    """Redis存储实现（生产推荐），Key规范见 constants.KEY_*"""

    def __init__(self, url: str):
        self._redis = aioredis.from_url(url, decode_responses=True)
        # 查状态→标记used，单Lua脚本保证原子（设计方案 §6.2 第4步）
        self._consume_script = self._redis.register_script("""
            local v = redis.call('GET', KEYS[1])
            if not v then return '__missing__' end
            local obj = cjson.decode(v)
            if tonumber(obj['status']) ~= 1 then return '__used__|' .. v end
            obj['status'] = 2
            obj['used_at'] = tonumber(ARGV[1])
            redis.call('SET', KEYS[1], cjson.encode(obj), 'KEEPTTL')
            return '__ok__|' .. v
        """)
        # INCR+EXPIRE原子化（登录失败计数）：保证计数key始终带TTL，避免残留永久key
        self._incr_script = self._redis.register_script("""
            local v = redis.call('INCR', KEYS[1])
            if v == 1 or redis.call('TTL', KEYS[1]) < 0 then
                redis.call('EXPIRE', KEYS[1], ARGV[1])
            end
            return v
        """)

    async def get_json(self, key: str) -> Optional[dict]:
        raw = await self._redis.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, data: dict, ttl: int) -> None:
        await self._redis.set(key, json.dumps(data), ex=ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._redis.exists(key))

    async def add_to_set(self, key: str, member: str, ttl: int) -> None:
        # Redis的set无成员级TTL：索引TTL取最大寿命，过期成员读取时按RT记录是否存在过滤
        await self._redis.sadd(key, member)
        await self._redis.expire(key, ttl)

    async def remove_from_set(self, key: str, member: str) -> None:
        await self._redis.srem(key, member)

    async def get_set(self, key: str) -> list[str]:
        return list(await self._redis.smembers(key))

    async def delete_set(self, key: str) -> None:
        await self._redis.delete(key)

    async def get_string(self, key: str) -> Optional[str]:
        return await self._redis.get(key)

    async def set_string(self, key: str, value: str, ttl: int) -> None:
        await self._redis.set(key, value, ex=ttl)

    async def incr_with_ttl(self, key: str, ttl: int) -> int:
        """原子自增并保证TTL：单Lua脚本（INCR+首次/缺TTL时EXPIRE）"""
        result = await self._incr_script(keys=[key], args=[ttl])
        return int(result)

    async def consume_rt(self, key: str, now_ts: int) -> tuple[Optional[dict], bool]:
        result = await self._consume_script(keys=[key], args=[now_ts])
        if result == _RT_MISSING:
            return None, False
        marker, _, raw = result.partition('|')
        record = json.loads(raw)
        return record, marker == _RT_USED

    async def close(self) -> None:
        await self._redis.aclose()


def _build_store() -> MemoryStore | RedisStore:
    """按配置选择存储：REDIS_URL优先，留空降级内存（仅限本地开发）"""
    if settings.REDIS_URL:
        return RedisStore(settings.REDIS_URL)
    return MemoryStore()


auth_store = _build_store()


# ---------------- 语义化封装：业务层不直接拼Key ----------------
def session_key(sid: str) -> str:
    return KEY_SESSION.format(sid=sid)


def rt_key(token_hash: str) -> str:
    return KEY_RT.format(token_hash=token_hash)


def blacklist_key(jti: str) -> str:
    return KEY_BLACKLIST.format(jti=jti)


def user_tv_key(user_id: int) -> str:
    return KEY_USER_TV.format(user_id=user_id)


def family_key(family_id: str) -> str:
    return KEY_FAMILY.format(family_id=family_id)


def user_sessions_key(user_id: int) -> str:
    return KEY_USER_SESSIONS.format(user_id=user_id)


def grace_key(token_hash: str) -> str:
    return KEY_GRACE.format(token_hash=token_hash)


def login_fail_key(account: str) -> str:
    return KEY_LOGIN_FAIL.format(account=account)


def login_lock_key(account: str) -> str:
    return KEY_LOGIN_LOCK.format(account=account)
