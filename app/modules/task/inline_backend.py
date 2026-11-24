"""内联后端：无 Redis 的本地开发降级实现（与认证存储的降级策略一致）

提交即调度：enqueue 时直接在当前进程后台协程执行任务，不落队列。
对外语义与真实后端一致（返回job_id、异常不扩散到提交方），仅限本地开发/单实例部署。
"""

import asyncio
import logging
import uuid
from typing import Optional

from modules.task.base import TaskBackend

log = logging.getLogger(__name__)


class InlineBackend(TaskBackend):
    """进程内直接执行实现"""

    name = 'inline'

    def __init__(self):
        # task -> payload 映射：支持按payload清理（文件删除时取消在途任务）
        self._tasks: dict[asyncio.Task, dict] = {}

    async def enqueue(self, task_type: str, payload: dict, opts: Optional[dict] = None) -> str:
        from modules.task.registry import dispatch

        job_id = uuid.uuid4().hex
        task = asyncio.create_task(self._run(job_id, task_type, payload, dispatch))
        self._tasks[task] = payload
        task.add_done_callback(self._tasks.pop)
        return job_id

    async def _run(self, job_id: str, task_type: str, payload: dict, dispatch) -> None:
        try:
            await dispatch(task_type, payload)
            log.info("inline任务完成: job_id=%s type=%s", job_id, task_type)
        except Exception:
            # 任务异常仅记录日志，不影响提交方（与队列后端"失败可查可重试"语义对齐）
            log.exception("inline任务失败: job_id=%s type=%s", job_id, task_type)

    async def start_consumer(self, concurrency: int = 1) -> None:
        # 提交即调度，无需常驻消费
        pass

    async def purge_file_jobs(self, file_id: str) -> int:
        """取消该文件仍在执行中的inline任务"""
        removed = 0
        for task, payload in list(self._tasks.items()):
            if (payload or {}).get('fileId') == str(file_id):
                task.cancel()
                self._tasks.pop(task, None)
                removed += 1
        return removed

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()
