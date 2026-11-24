import os

# KAG(knext/aliyun-log)的预生成 _pb2 为旧式descriptor，与 protobuf>=4 的 C++ 实现不兼容，
# 必须在进程内任何 protobuf import 前切到纯 Python 实现（对 pymilvus 等新式 pb2 同样兼容）
os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from config.settings import settings
from core.exceptions import BusinessError, ServiceException
from core.log_config import setup_logger, unify_uvicorn_access_log
from common.response import ResponseObject
from api.document_api import kb_api as document_kb_router
from api.document_api import file_api as document_file_router
from api.retriever_api import api as retriever_router
from api.provider_api import api as provider_router
from api.auth_api import api as auth_router
from api.team_api import api as team_router
from api.team_api import project_api as project_router
from api.team_api import kb_api as kb_router
from api.team_api import account_api as account_router
from modules.auth.middleware import AuthMiddleware
from modules.task.backend import close_task_backend, get_task_backend

# 初始化日志（自定义格式+trace_id注入+文件滚动），需在获取logger前执行
setup_logger()

log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # uvicorn的dictConfig可能晚于setup_logger执行，启动时再统一一次访问日志格式
    unify_uvicorn_access_log()
    log.info("应用启动中...")
    # MCP会话管理器：挂载的子应用lifespan不会自动执行，须手动启动（mcp_server.py）
    await mcp_server.start_session_manager()
    # 任务消费并入应用进程：单服务部署，不再需要独立 worker 进程
    backend = get_task_backend()
    await backend.start_consumer(concurrency=settings.TASK_CONCURRENCY)
    log.info("任务消费已启动: backend=%s concurrency=%s", backend.name, settings.TASK_CONCURRENCY)
    log.info("组件启动成功...")
    log.info("应用启动成功...")
    yield
    log.info("应用关闭中...")
    await mcp_server.stop_session_manager()
    await close_task_backend()
    log.info("组件关闭成功...")
    log.info("应用关闭成功...")
app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

#开启日志链路追踪
FastAPIInstrumentor.instrument_app(app)

# 注册业务模块路由
app.include_router(document_kb_router)
app.include_router(document_file_router)
app.include_router(retriever_router)
app.include_router(provider_router)
app.include_router(auth_router)
app.include_router(team_router)
app.include_router(project_router)
app.include_router(kb_router)
app.include_router(account_router)

# 统一鉴权拦截器：除公开路径外全部经过多层校验（modules/auth/middleware.py）
app.add_middleware(AuthMiddleware)

# MCP服务：知识库检索工具暴露给外部Agent（POST /mcp，见 mcp_server.py）。
# 挂载到根路径、由子应用内部路由 /mcp 精确匹配（避免挂载点路径拼接的307重定向）
from mcp_server import mcp_app  # noqa: E402  放在鉴权注册后挂载，路径已在白名单开放
import mcp_server  # noqa: E402
app.mount('', mcp_app)


### 全局异常处理器 ###
@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    """业务异常：按业务错误码返回对应HTTP状态码（400/401/403/404/409等）"""
    log.warning("业务异常: code=%s message=%s", exc.code, exc.message)
    error_response = ResponseObject(success=False, code=exc.code, message=exc.message)
    return JSONResponse(status_code=exc.status_code, content=error_response.model_dump())


@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    """处理自定义服务异常"""
    # logger.error(f"ServiceException: {str(exc)}")
    log.exception("业务异常！")

    error_response = ResponseObject(
        success=False,
        message=exc.message
    )

    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """处理所有未捕获的异常"""
    log.exception(f"未知异常！")

    error_response = ResponseObject(
        success=False,
        message=str(exc)
    )

    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)