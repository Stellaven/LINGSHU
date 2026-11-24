"""统一鉴权拦截器（设计方案 §7）

所有受保护接口必须经过本拦截器，校验顺序不可调换：
  1. 取AT  2. JWT验签  3. exp  4. jti黑名单  5. 会话状态  6. token_version  7. 用户status

滑动窗口续期（设计方案 §8.1）：AT剩余有效期低于阈值时自动签发新AT，
通过 X-New-Access-Token 响应头返回，前端静默替换，不消耗RT。
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from common.response import ResponseObject
from config.settings import settings
from modules.auth import security, service
from modules.auth.constants import CODE_TOKEN_INVALID, NEW_AT_EXPIRES_HEADER, NEW_AT_HEADER

# 无需鉴权的路径：登录/注册/续期/退出（退出幂等，凭签名定位会话）、密码公钥下发、探活、OpenAPI文档
_PUBLIC_PATHS = {'/', '/auth/login', '/auth/register', '/auth/refresh', '/auth/logout', '/auth/public-key',
                 '/docs', '/redoc', '/openapi.json', '/favicon.ico',
                 '/mcp'}  # MCP服务端点（外部Agent接入，如需收紧改用MCPServer的token校验）
_PUBLIC_PREFIXES = ('/hello',)


def is_public_path(path: str) -> bool:
    return path in _PUBLIC_PATHS or path.startswith(_PUBLIC_PREFIXES)


def _auth_error_response(message: str, code: int, status_code: int) -> JSONResponse:
    body = ResponseObject(success=False, code=code, message=message)
    return JSONResponse(status_code=status_code, content=body.model_dump())


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if is_public_path(request.url.path) or request.method == 'OPTIONS':
            return await call_next(request)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return _auth_error_response('未登录或令牌缺失', CODE_TOKEN_INVALID, 401)
        token = auth_header[7:].strip()

        try:
            # 2~7层校验（验签/exp/黑名单/会话/版本号/用户状态）在service内按序执行
            ctx = await service.authenticate(token)
        except Exception as exc:
            return self._to_error_response(exc)

        request.state.user_id = ctx.user_id
        request.state.account = ctx.account
        request.state.sid = ctx.sid

        # 滑动窗口续期：AT剩余有效期不足阈值时签发新AT（不消耗RT）
        renew_at = None
        if ctx.exp - int(time.time()) < settings.RENEW_THRESHOLD:
            renew_at = security.create_access_token(ctx.user_id, ctx.sid, ctx.token_version)

        response = await call_next(request)
        if renew_at:
            response.headers[NEW_AT_HEADER] = renew_at
            response.headers[NEW_AT_EXPIRES_HEADER] = str(settings.AT_TTL)
        return response

    @staticmethod
    def _to_error_response(exc: Exception) -> JSONResponse:
        from core.exceptions import BusinessError
        if isinstance(exc, BusinessError):
            return _auth_error_response(exc.message, exc.code, exc.status_code)
        # Redis宕机等存储不可用：fail closed，拒绝请求而非放行（设计方案 §11）
        raise exc
