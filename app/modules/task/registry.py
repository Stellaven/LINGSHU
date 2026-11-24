"""任务执行器注册表：task_type -> 处理函数

任务模块只负责调度，具体执行逻辑由各业务模块注册（解耦）；
内置执行器见 handlers.py（import 即注册），inline 降级与 worker 消费统一走 dispatch。
"""

import logging
from typing import Awaitable, Callable, Optional

log = logging.getLogger(__name__)

# 任务执行器：payload -> 协程
TaskHandler = Callable[[dict], Awaitable[None]]

_handlers: dict[str, TaskHandler] = {}


def register_handler(task_type: str, handler: TaskHandler) -> None:
    """注册任务执行器（同类型重复注册覆盖，便于测试替换）"""
    _handlers[task_type] = handler


def get_handler(task_type: str) -> Optional[TaskHandler]:
    return _handlers.get(task_type)


async def dispatch(task_type: str, payload: dict) -> None:
    """按任务类型调度执行；未注册执行器视为任务失败（由后端记录/重试）"""
    handler = get_handler(task_type)
    if handler is None:
        raise RuntimeError(f"任务执行器未注册: {task_type}")
    await handler(payload)
