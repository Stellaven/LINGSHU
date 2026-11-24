"""任务队列后端适配器接口（适配器模式）

统一「提交/消费/释放」语义，屏蔽底层任务框架差异：
- bullmq：Redis + BullMQ 官方 Python 版（当前默认，key布局与JS生态互通）
- inline：无 Redis 时进程内直接执行的降级实现（仅限本地开发）

后续更换任务框架（Celery/ARQ 等）只需新增 Backend 实现并登记到 backend.py 工厂，
业务层（service.py）与执行器（handlers.py）零改动。
"""

from abc import ABC, abstractmethod
from typing import Optional


class TaskBackend(ABC):
    """任务队列后端接口"""

    # 后端标识（日志与监控用）
    name: str = 'base'

    @abstractmethod
    async def enqueue(self, task_type: str, payload: dict, opts: Optional[dict] = None) -> str:
        """提交任务，返回框架生成的任务ID"""

    @abstractmethod
    async def start_consumer(self, concurrency: int = 1) -> None:
        """启动消费（inline为空操作；应用启动时调用）"""

    @abstractmethod
    async def close(self) -> None:
        """释放连接与后台任务"""

    async def purge_file_jobs(self, file_id: str) -> int:
        """清除队列中属于该文件的任务（文件删除时调用，防删除后任务仍被消费重放）

        返回清除的任务数；正在执行的任务由具体后端尽力处理（无法中断时跳过）。
        非抽象默认实现：不支持清理的后端返回0。
        """
        return 0
