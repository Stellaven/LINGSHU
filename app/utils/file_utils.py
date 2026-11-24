"""文件上传下载工具：基于 MinIO 对象存储

- 客户端懒创建（首用时连接），bucket 不存在时自动创建（本地开发友好）
- MinIO SDK 为同步实现，统一经 asyncio.to_thread 调用，避免阻塞事件循环
- 对象key约定：uploads/yyyyMMdd/uuid.ext（保留原扩展名，防同名覆盖）
"""

import asyncio
import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from config.settings import settings

log = logging.getLogger(__name__)

_client = None


def _get_client():
    """懒创建 MinIO 客户端（长驻连接，线程安全）"""
    global _client
    if _client is None:
        from minio import Minio  # 懒导入：非文件链路不承担SDK加载开销

        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


async def _ensure_bucket() -> None:
    """bucket不存在时自动创建"""
    client = _get_client()
    bucket = settings.MINIO_BUCKET
    if not await asyncio.to_thread(client.bucket_exists, bucket):
        await asyncio.to_thread(client.make_bucket, bucket)
        log.info("MinIO bucket已创建: %s", bucket)


def build_object_name(file_name: str) -> str:
    """生成对象key：uploads/yyyyMMdd/uuid.ext（保留原扩展名）"""
    ext = os.path.splitext(file_name or '')[1]
    return f"uploads/{datetime.now(timezone.utc):%Y%m%d}/{uuid.uuid4().hex}{ext}"


def _guess_content_type(file_name: str, explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    return mimetypes.guess_type(file_name or '')[0] or 'application/octet-stream'


async def upload_bytes(
    data: bytes, file_name: str,
    object_name: Optional[str] = None, content_type: Optional[str] = None,
) -> dict:
    """上传内存数据（如FastAPI UploadFile读取结果），返回对象信息"""
    await _ensure_bucket()
    object_name = object_name or build_object_name(file_name)
    content_type = _guess_content_type(file_name, content_type)
    client = _get_client()
    await asyncio.to_thread(
        client.put_object, settings.MINIO_BUCKET, object_name,
        BytesIO(data), len(data), content_type=content_type,
    )
    log.info("文件已上传MinIO: %s (%s bytes)", object_name, len(data))
    return {
        'objectName': object_name,
        'bucket': settings.MINIO_BUCKET,
        'size': len(data),
        'contentType': content_type,
    }


async def upload_file(
    local_path: str, file_name: Optional[str] = None,
    object_name: Optional[str] = None, content_type: Optional[str] = None,
) -> dict:
    """上传本地文件（流式，不占内存），返回对象信息"""
    await _ensure_bucket()
    file_name = file_name or os.path.basename(local_path)
    object_name = object_name or build_object_name(file_name)
    content_type = _guess_content_type(file_name, content_type)
    client = _get_client()
    await asyncio.to_thread(
        client.fput_object, settings.MINIO_BUCKET, object_name,
        local_path, content_type=content_type,
    )
    size = os.path.getsize(local_path)
    log.info("本地文件已上传MinIO: %s (%s bytes)", object_name, size)
    return {
        'objectName': object_name,
        'bucket': settings.MINIO_BUCKET,
        'size': size,
        'contentType': content_type,
    }


async def download_file(object_name: str, local_path: str) -> str:
    """下载对象到本地路径，返回本地路径"""
    client = _get_client()
    os.makedirs(os.path.dirname(local_path) or '.', exist_ok=True)
    await asyncio.to_thread(client.fget_object, settings.MINIO_BUCKET, object_name, local_path)
    log.info("文件已从MinIO下载: %s -> %s", object_name, local_path)
    return local_path


async def delete_file(object_name: str) -> None:
    """删除对象（对象不存在时静默成功，与S3语义一致）"""
    client = _get_client()
    await asyncio.to_thread(client.remove_object, settings.MINIO_BUCKET, object_name)
    log.info("文件已从MinIO删除: %s", object_name)


async def get_object_response(object_name: str):
    """获取对象可读流（供接口层StreamingResponse透传，调用方负责关闭）"""
    client = _get_client()
    return await asyncio.to_thread(client.get_object, settings.MINIO_BUCKET, object_name)


async def get_presigned_url(object_name: str, expires_seconds: int = 3600) -> str:
    """生成预签名下载URL（前端直连MinIO下载用）"""
    client = _get_client()
    from datetime import timedelta
    return await asyncio.to_thread(
        client.presigned_get_object, settings.MINIO_BUCKET, object_name,
        expires=timedelta(seconds=expires_seconds),
    )
