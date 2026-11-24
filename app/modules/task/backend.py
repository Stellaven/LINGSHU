"""任务后端工厂：按配置装配具体框架实现（单例）

装配规则：
- TASK_BACKEND=bullmq（默认）：Redis + BullMQ，生产/联调使用
- TASK_BACKEND=inline：进程内直接执行
- REDIS_URL 未配置时无论 TASK_BACKEND 取值均强制降级 inline

单服务模式：app 进程启动时同时启动消费（main.py lifespan），
本进程既提交也消费，无需独立 worker 进程。
更换任务框架：新增 TaskBackend 实现并在此登记即可，业务层无感知。
"""

from config.settings import settings
from modules.task import handlers  # noqa: F401  import即注册内置执行器（本进程消费需要）
from modules.task.base import TaskBackend
from modules.task.constants import QUEUE_FILE_PROCESS
from modules.task.inline_backend import InlineBackend

_backend: TaskBackend | None = None


def get_task_backend() -> TaskBackend:
    global _backend
    if _backend is None:
        if settings.TASK_BACKEND == 'inline' or not settings.REDIS_URL:
            _backend = InlineBackend()
        else:
            from modules.task.bullmq_backend import BullMQBackend  # 懒导入框架实现

            _backend = BullMQBackend(queue_name=QUEUE_FILE_PROCESS, redis_url=settings.REDIS_URL)
    return _backend


async def close_task_backend() -> None:
    """释放后端资源（应用shutdown时调用）"""
    global _backend
    if _backend is not None:
        await _backend.close()
        _backend = None
