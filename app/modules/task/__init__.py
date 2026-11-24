"""文件处理任务模块：适配器模式封装任务队列，供上传等链路提交任务

对外入口：
- submit_file_parse_task：提交文件解析任务（上传落盘+选定策略后调用）
- registry.register_handler：业务模块注册自定义任务执行器

后端装配见 backend.py（当前 BullMQ，无Redis时降级进程内执行）；
单服务模式：消费随 app 进程启动（main.py lifespan），无独立 worker 进程。
"""

from modules.task.registry import register_handler
from modules.task.service import submit_file_parse_task

__all__ = ['submit_file_parse_task', 'register_handler']
