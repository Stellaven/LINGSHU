"""Docling解析服务封装：调用本地docling-serve HTTP服务将文件转换为Markdown

文件处理策略 parser=Docling 时由 process_file 调用；解析结果以单个
llama_index Document 返回（Markdown文本），后续切分仍走策略 stages 的分块配置。
服务地址与超时从 settings（DOCLING_BASE_URL / DOCLING_TIMEOUT）读取。
"""

import logging
import os

import httpx
from llama_index.core.schema import Document

from config.settings import settings

log = logging.getLogger(__name__)

class DoclingParseError(Exception):
    """Docling解析失败（网络、服务错误或响应格式异常）"""


async def parse_file(file_path: str) -> list[Document]:
    """调用docling-serve解析本地文件，返回带Markdown文本的Document列表

    docling-serve接口：POST /v1/convert/source（multipart，files字段），
    默认输出格式为Markdown。返回单文档列表（docling将整个文件转换为一篇文档）。
    """
    payload = await _convert(file_path)
    document = payload.get('document') or {}
    text = document.get('md_content') or document.get('text_content') or ''
    if not text.strip():
        raise DoclingParseError(f"Docling返回空内容: {os.path.basename(file_path)}")
    return [Document(text=text)]


async def _convert(file_path: str) -> dict:
    """上传文件到docling-serve并返回转换结果JSON"""
    filename = os.path.basename(file_path)
    timeout = httpx.Timeout(settings.DOCLING_CONNECT_TIMEOUT, read=settings.DOCLING_TIMEOUT)
    try:
        with open(file_path, 'rb') as f:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f'{settings.DOCLING_BASE_URL.rstrip("/")}/v1/convert/source',
                    files={'files': (filename, f)},
                )
    except httpx.HTTPError as exc:
        raise DoclingParseError(f'Docling服务请求失败: {exc}') from exc

    if resp.status_code != 200:
        raise DoclingParseError(
            f'Docling服务返回异常状态 {resp.status_code}: {resp.text[:200]}')
    try:
        payload = resp.json()
    except ValueError as exc:
        raise DoclingParseError('Docling服务响应非JSON格式') from exc

    # status: ok 全部成功；partial 部分页失败（仍返回可用内容，仅记录告警）
    status = payload.get('status')
    if status == 'failure':
        raise DoclingParseError(f'Docling解析失败: {filename}')
    if status == 'partial':
        log.warning('Docling部分解析成功（partial）: file=%s', filename)
    return payload
