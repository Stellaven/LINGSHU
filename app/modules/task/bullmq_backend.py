"""BullMQ 后端适配器：基于 BullMQ 官方 Python 版（Redis 队列）

与 Node.js BullMQ 完全互通（相同 key 布局），后续可用 JS worker 并行消费。
Queue/Worker 均懒创建（bullmq 框架只在用到时加载），close 时统一释放。
"""

import logging
from typing import Optional

from config.settings import settings
from modules.task.base import TaskBackend

log = logging.getLogger(__name__)

# 默认任务选项：失败自动重试（指数退避），成功即清理、失败保留最近N条便于排障
DEFAULT_JOB_OPTS = {
    'attempts': settings.TASK_MAX_ATTEMPTS,
    'backoff': {'type': 'exponential', 'delay': settings.TASK_BACKOFF_DELAY},
    'removeOnComplete': True,
    'removeOnFail': settings.TASK_KEEP_FAILED,
}


class BullMQBackend(TaskBackend):
    """BullMQ(Redis) 实现"""

    name = 'bullmq'

    def __init__(self, queue_name: str, redis_url: str):
        self._queue_name = queue_name
        self._redis_url = redis_url
        self._queue = None
        self._worker = None

    async def _get_queue(self):
        """懒创建 Queue（长驻连接，进程退出时关闭）"""
        if self._queue is None:
            from bullmq import Queue  # 懒导入：非任务链路不承担框架加载开销

            self._queue = Queue(self._queue_name, {'connection': self._redis_url})
        return self._queue

    async def enqueue(self, task_type: str, payload: dict, opts: Optional[dict] = None) -> str:
        queue = await self._get_queue()
        job = await queue.add(task_type, payload, {**DEFAULT_JOB_OPTS, **(opts or {})})
        return str(job.id)

    async def start_consumer(self, concurrency: int = 1) -> None:
        from bullmq import Worker  # 懒导入同上
        from modules.task.registry import dispatch

        async def _processor(job, job_token):
            # BullMQ 约定：处理器异常视为任务失败，由框架按 attempts 重试
            await dispatch(job.name, job.data)

        self._worker = Worker(
            self._queue_name, _processor,
            {'connection': self._redis_url, 'concurrency': concurrency},
        )
        # Worker 默认 autorun=True，构造后已在后台事件循环中开始消费
        log.info("BullMQ worker已启动: queue=%s concurrency=%s", self._queue_name, concurrency)

    async def purge_file_jobs(self, file_id: str) -> int:
        """清除队列中属于该文件的任务：waiting/delayed/failed/completed全扫，
        active任务BullMQ不支持移除（try/except跳过，由消费方兜底）"""
        queue = await self._get_queue()
        removed = 0
        for job in await queue.getJobs(['waiting', 'delayed', 'failed', 'completed', 'active']):
            if job is None or (job.data or {}).get('fileId') != str(file_id):
                continue
            try:
                await job.remove()
                removed += 1
            except Exception:
                log.warning("清理文件任务失败（可能正在执行）: job_id=%s file_id=%s", job.id, file_id)
        return removed

    async def close(self) -> None:
        if self._worker is not None:
            await self._worker.close()
            self._worker = None
        if self._queue is not None:
            await self._queue.close()
            self._queue = None
