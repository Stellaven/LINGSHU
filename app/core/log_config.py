import logging
import os
from logging.handlers import TimedRotatingFileHandler

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from config.settings import settings


class TraceLogFormatter(logging.Formatter):
    """
    自定义日志格式：
    时间戳 | 线程名 | trace_id | span_id | 级别 | 文件名 | 日志内容
    """

    def __init__(self):
        super().__init__(
            fmt=(
                "%(asctime)s | "
                "%(threadName)s | "
                "%(trace_id)s | "
                "%(span_id)s | "
                "%(levelname)s | "
                "%(filename)s | "
                "%(message)s"
            )
        )

    def format(self, record):
        # 自动注入 trace_id
        span = trace.get_current_span()
        if span and span.get_span_context().trace_id:
            record.trace_id = format(span.get_span_context().trace_id, "016x")
            record.span_id = format(span.get_span_context().span_id, "016x")
        else:
            record.trace_id = "0"
            record.span_id = "0"
        return super().format(record)


def setup_logger():
    _base_config()
    unify_uvicorn_access_log()
    init_otel()


def _base_config():
    # 确保日志目录存在
    log_path = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_path, exist_ok=True)

    # 根日志器
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    logger.handlers.clear()  # 清空默认

    # ===================== 1. 控制台输出 =====================
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(TraceLogFormatter())
    logger.addHandler(console_handler)

    # ===================== 2. 文件输出（按天滚动） =====================
    log_file = os.path.join(log_path, "app.log")
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",  # 每天零点回滚（标准库不支持按月）
        interval=1,
        backupCount=settings.LOG_RETENTION_DAYS,  # 保留天数走配置
        encoding="utf-8",
        delay=True
    )
    file_handler.setFormatter(TraceLogFormatter())
    logger.addHandler(file_handler)

    # ===================== 3. uvicorn访问日志统一格式 =====================
    # 见 unify_uvicorn_access_log：main.py的lifespan启动时也会再执行一次，
    # 覆盖「python main.py」启动时uvicorn dictConfig晚于本函数的场景
    unify_uvicorn_access_log()


def unify_uvicorn_access_log():
    """uvicorn自带的loggers（uvicorn/uvicorn.access/uvicorn.error）各挂了内置handler
    （INFO: x.x.x.x - "GET / 200" 等）且propagate=False，与root上的统一格式割裂。
    注意access记录会先经过父logger「uvicorn」再到root，因此整条链都要清handler、开传播，
    让记录统一流经root的TraceLogFormatter（控制台+文件）"""
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def init_otel():
    trace.set_tracer_provider(TracerProvider())
