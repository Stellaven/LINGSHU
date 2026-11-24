import logging
from typing import Optional

from fastapi import APIRouter, Request, Response

from common.response import ResponseObject
from modules.auth import rsa_cipher, service
from modules.auth.constants import RT_COOKIE_NAME
from modules.auth.schema import ChangePasswordRequest, LoginRequest, RefreshRequest, RegisterRequest
from config.settings import settings

api = APIRouter(prefix="/auth")

log = logging.getLogger(__name__)


def _set_rt_cookie(response: Response, refresh_token: str) -> None:
    """Web端RT只走HttpOnly Cookie：禁止localStorage/URL/日志（设计方案 §4.2）"""
    response.set_cookie(
        RT_COOKIE_NAME,
        refresh_token,
        max_age=settings.RT_SLIDING_TTL,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite='lax',
        path=settings.AUTH_COOKIE_PATH,
    )


def _pop_rt(bundle) -> dict:
    """RT仅通过Cookie下发，body中剥离，避免Web端意外存储"""
    data = bundle.model_dump(exclude_none=True)
    data.pop('refresh_token', None)
    return data


@api.get('/public-key')
async def public_key():
    """下发密码传输加密公钥（由私钥派生，保证配对）；公钥本身非敏感，可公开"""
    return ResponseObject(data={'public_key': rsa_cipher.get_public_key_pem()})


@api.post('/register')
async def register(req: RegisterRequest):
    log.info("用户注册: account=%s", req.account)
    # 密码密文解密还原明文（明文长度校验在解密层，min 6位）
    password = rsa_cipher.decrypt_password(req.password, min_length=6)
    user = await service.register(req.account, password)
    return ResponseObject(data=user)


@api.post('/login')
async def login(req: LoginRequest, response: Response, request: Request):
    log.info("用户登录: account=%s", req.account)
    ip = request.client.host if request.client else None
    password = rsa_cipher.decrypt_password(req.password)
    bundle = await service.login(req.account, password, req.device_id, ip)
    _set_rt_cookie(response, bundle.refresh_token)
    return ResponseObject(data=_pop_rt(bundle))


@api.post('/refresh')
async def refresh(request: Request, response: Response, req: Optional[RefreshRequest] = None):
    # Web端从HttpOnly Cookie取RT，App端从body取（设计方案 §6.2）；body可为空（纯Cookie场景）
    rt = request.cookies.get(RT_COOKIE_NAME) or (req.refresh_token if req else None)
    ip = request.client.host if request.client else None
    bundle = await service.refresh(rt, ip)
    _set_rt_cookie(response, bundle.refresh_token)
    return ResponseObject(data=_pop_rt(bundle))


@api.post('/logout')
async def logout(request: Request, response: Response):
    auth_header = request.headers.get('Authorization', '')
    token = auth_header[7:].strip() if auth_header.startswith('Bearer ') else None
    await service.logout(token)
    # 清除RT Cookie（幂等：重复退出也返回成功）
    response.delete_cookie(RT_COOKIE_NAME, path=settings.AUTH_COOKIE_PATH)
    return ResponseObject(message='已退出登录')


@api.post('/password')
async def change_password(req: ChangePasswordRequest, request: Request, response: Response):
    # 经统一拦截器校验后注入user_id（非公开路径）
    user_id = request.state.user_id
    log.info("用户修改密码: user_id=%s", user_id)
    ip = request.client.host if request.client else None
    # 新旧密码均为密文，解密后校验新密码明文长度（min 6位）
    old_password = rsa_cipher.decrypt_password(req.old_password)
    new_password = rsa_cipher.decrypt_password(req.new_password, min_length=6)
    bundle = await service.change_password(user_id, old_password, new_password, ip)
    # 当前设备重新签发：下发新AT(body)+新RT(Cookie)
    _set_rt_cookie(response, bundle.refresh_token)
    return ResponseObject(data=_pop_rt(bundle))
