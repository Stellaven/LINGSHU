"""知识库文件业务层：上传（存MinIO→登记→提交异步解析任务）、列表、下载

权限：与策略域一致，仅知识库所属项目的成员可操作。
"""

import logging
from typing import Optional
from urllib.parse import quote

from fastapi import UploadFile

from core.exceptions import BusinessError
from modules.document import file_repository, strategy_repository, strategy_service
from utils import file_utils

log = logging.getLogger(__name__)

CODE_FILE_NOT_FOUND = 40409  # 文件不存在（HTTP 404）


async def upload_kb_files(
    kb_id: int, user_id: int, files: list[UploadFile], strategy_id: Optional[int] = None,
) -> list[dict]:
    """批量上传文件至知识库：逐个存MinIO→登记kb_files→提交file.parse任务"""
    await strategy_service._require_kb_member(kb_id, user_id)
    if strategy_id is not None:
        # 提交前校验策略归属（worker消费时会回读最新配置）
        strategy = await strategy_repository.get_strategy(kb_id, strategy_id)
        if not strategy:
            raise BusinessError('策略不存在',
                                code=strategy_service.CODE_STRATEGY_NOT_FOUND, status_code=404)

    # 懒导入任务模块，避免import期加载任务域
    from modules.task import submit_file_parse_task

    results = []
    for f in files:
        data = await f.read()
        info = await file_utils.upload_bytes(data, f.filename)
        record = await file_repository.create_file(
            kb_id=kb_id, file_name=f.filename, object_name=info['objectName'],
            bucket=info['bucket'], size=info['size'], content_type=info['contentType'],
            strategy_id=strategy_id, uploaded_by=user_id,
        )
        await submit_file_parse_task(
            file_name=f.filename, object_name=info['objectName'], bucket=info['bucket'],
            kb_id=kb_id, strategy_id=strategy_id, user_id=user_id, file_id=record['id'],
        )
        results.append(record)
        log.info("文件已上传并提交解析: kb_id=%s file=%s object=%s size=%s",
                 kb_id, f.filename, info['objectName'], info['size'])
    return results


async def list_kb_files(kb_id: int, user_id: int) -> list[dict]:
    """知识库内文件列表"""
    await strategy_service._require_kb_member(kb_id, user_id)
    return await file_repository.list_files(kb_id)


async def get_file_stream(file_id: int, user_id: int):
    """文件原内容流（下载用）：返回 (MinIO响应流, 文件名, content_type)"""
    record = await file_repository.get_file(file_id)
    if not record:
        raise BusinessError('文件不存在', code=CODE_FILE_NOT_FOUND, status_code=404)
    # 文件归属校验：所在知识库的项目成员可下载
    await strategy_service._require_kb_member(int(record['kbId']), user_id)
    stream = await file_utils.get_object_response(record['objectName'])
    return stream, record['name'], record['contentType']


def content_disposition(file_name: str) -> str:
    """附件下载头（文件名含中文时按RFC5987编码）"""
    return f"attachment; filename*=UTF-8''{quote(file_name)}"


async def get_file_chunks(file_id: int, user_id: int, page: int, page_size: int) -> dict:
    """文件分块预览（docstore切分节点，分页）；仅解析成功后有数据"""
    record = await file_repository.get_file(file_id)
    if not record:
        raise BusinessError('文件不存在', code=CODE_FILE_NOT_FOUND, status_code=404)
    await strategy_service._require_kb_member(int(record['kbId']), user_id)
    return await file_repository.list_file_chunks(file_id, page, page_size)


async def delete_kb_file(file_id: int, user_id: int) -> None:
    """删除知识库文件：清理解析任务(Redis)→MinIO对象→向量与分块→kb_files记录

    删除顺序：先摘除队列任务防止删除后任务仍被消费重放；kb_files记录最后删，
    中途失败时记录仍可见，可重试删除。
    """
    record = await file_repository.get_file(file_id)
    if not record:
        raise BusinessError('文件不存在', code=CODE_FILE_NOT_FOUND, status_code=404)
    # 文件归属校验：所在知识库的项目成员可删除
    await strategy_service._require_kb_member(int(record['kbId']), user_id)

    # 1. Redis：清除该文件的解析任务（BullMQ job / inline在途任务）
    from modules.task.backend import get_task_backend

    purged = await get_task_backend().purge_file_jobs(record['id'])

    # 2. MinIO对象（不存在时静默成功，与S3语义一致）
    await file_utils.delete_file(record['objectName'])

    # 3. 向量与分块（Milvus collection + PG docstore）
    from modules.document import service as document_service

    file_key = document_service.build_file_key(record['id'], record['objectName'])
    await document_service.delete_file_chunks(f"kb_{record['kbId']}", file_key, kb_id=record['kbId'])

    # 4. kb_files记录
    await file_repository.delete_file(file_id)
    log.info("文件删除完成: file_id=%s kb_id=%s name=%s purged_jobs=%s",
             file_id, record['kbId'], record['name'], purged)
