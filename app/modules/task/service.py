"""文件处理任务业务封装：供上传等链路提交任务

使用时机：文件已上传MinIO + 用户已选定处理策略（可选）之后。
任务本体（job）由所选后端托管；payload 携带文件定位信息与策略引用，
执行器（handlers.py）消费时实时回读策略配置，保证用最新策略处理。
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from core.exceptions import BusinessError
from modules.task.backend import get_task_backend
from modules.task.constants import TASK_FILE_PARSE

log = logging.getLogger(__name__)

CODE_STRATEGY_NOT_FOUND = 40408  # 策略不存在（HTTP 404，与 document 域一致）


async def submit_file_parse_task(
    file_name: str, object_name: str, bucket: str,
    kb_id: int, strategy_id: Optional[int], user_id: int, file_id: Optional[str] = None,
) -> str:
    """提交文件解析任务，返回job_id（可用于状态查询与对账）

    - object_name/bucket：文件在对象存储中的定位（执行器先下载到临时文件再解析）
    - strategy_id：知识库内已创建的处理策略；提交时校验存在性，消费时回读最新配置；
      未指定时执行器按文件后缀默认切分
    - file_id：kb_files 记录ID，执行器完成后回写解析状态/分块数
    """
    # 懒导入 document 域：避免任务模块在 import 期反向耦合业务模块加载链
    if strategy_id is not None:
        from modules.document import strategy_repository

        strategy = await strategy_repository.get_strategy(kb_id, strategy_id)
        if not strategy:
            raise BusinessError('策略不存在', code=CODE_STRATEGY_NOT_FOUND, status_code=404)

    payload = {
        'taskId': uuid.uuid4().hex,
        'taskType': TASK_FILE_PARSE,
        'fileId': file_id,
        'kbId': kb_id,
        'strategyId': strategy_id,
        'userId': user_id,
        'file': {'name': file_name, 'objectName': object_name, 'bucket': bucket},
        'submittedAt': datetime.now(timezone.utc).isoformat(),
    }
    job_id = await get_task_backend().enqueue(TASK_FILE_PARSE, payload)
    log.info("文件解析任务已提交: job_id=%s file=%s kb_id=%s strategy_id=%s",
             job_id, file_name, kb_id, strategy_id)
    return job_id
