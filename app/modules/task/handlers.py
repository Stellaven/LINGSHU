"""内置任务执行器：import 即注册（app 进程消费与 inline 降级共用）

执行器只做「下载文件 + 回读配置 + 调用业务流水线 + 回写状态」，
具体解析逻辑留在 document 域；业务模块如需自定义任务类型，
可在各自模块内用 registry.register_handler 注册。
"""

import logging
import os
import tempfile

from modules.task import registry
from modules.task.constants import TASK_FILE_PARSE

log = logging.getLogger(__name__)


async def handle_file_parse(payload: dict) -> None:
    """文件解析入库：下载→回读策略→解析切分向量化→回写kb_files状态

    异常时标记failed并重新抛出，交由任务框架按attempts重试。
    """
    # 懒导入：重依赖（llama-index/torch等）只在任务真正执行时加载
    from modules.document import file_repository
    from modules.document import service as document_service
    from modules.document import strategy_repository
    from utils import file_utils

    file_id = payload.get('fileId')
    file_name = payload['file']['name']
    try:
        if file_id:
            await file_repository.mark_status(int(file_id), file_repository.FILE_STATUS_PROCESSING)

        strategy = None
        if payload.get('strategyId'):
            kb_id, strategy_id = payload['kbId'], payload['strategyId']
            strategy = await strategy_repository.get_strategy(kb_id, strategy_id)
            if not strategy:
                raise ValueError(f"策略不存在: kb_id={kb_id} strategy_id={strategy_id}")

        # 从对象存储下载到临时文件（解析完成后清理）
        suffix = os.path.splitext(file_name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
        try:
            await file_utils.download_file(payload['file']['objectName'], tmp_path)
            # 每个知识库一个Milvus collection，不覆盖已有数据；
            # file_key使重试/恢复重跑时可清除旧分块，保证幂等
            file_key = document_service.build_file_key(file_id, payload['file']['objectName'])
            chunk_count = await document_service.process_file(
                tmp_path, collection_name=f"kb_{payload['kbId']}", overwrite=False,
                strategy=strategy, file_key=file_key, kb_id=payload.get('kbId'),
            )
        finally:
            os.unlink(tmp_path)

        if file_id:
            await file_repository.mark_status(
                int(file_id), file_repository.FILE_STATUS_INDEXED, chunk_count=chunk_count)
        log.info("文件解析完成: file=%s chunk_count=%s", file_name, chunk_count)
    except Exception as exc:
        if file_id:
            try:
                await file_repository.mark_status(
                    int(file_id), file_repository.FILE_STATUS_FAILED, error=str(exc)[:500])
            except Exception:
                log.exception("解析状态回写失败: file_id=%s", file_id)
        raise


registry.register_handler(TASK_FILE_PARSE, handle_file_parse)
