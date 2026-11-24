import logging
from typing import Optional

from fastapi import APIRouter, Form, Request, UploadFile, File
from fastapi.responses import StreamingResponse

from common.response import ResponseObject
from modules.document import strategy_service
from modules.document import file_service
from modules.document import graph_schema_service
from modules.document.schema import (
    CreateParseStrategyRequest, SaveGraphSchemaRequest, UpdateParseStrategyRequest,
)

# 知识库维度资源路由（前端契约：/api/knowledge-bases/{kbId}/parse-strategies、/files）
kb_api = APIRouter(prefix="/knowledge-bases")
# 文件维度路由（前端契约：/api/files/{fileId}/content）
file_api = APIRouter(prefix="/files")

log = logging.getLogger(__name__)


@kb_api.post('/{kb_id}/files/upload')
async def upload_kb_files(
    kb_id: int, request: Request,
    files: list[UploadFile] = File(...), strategy_id: Optional[int] = Form(None),
):
    """上传文件至知识库：存MinIO→登记kb_files→提交异步解析任务（multipart, field: files）"""
    data = await file_service.upload_kb_files(kb_id, request.state.user_id, files, strategy_id)
    log.info("知识库文件上传: user_id=%s kb_id=%s count=%s strategy_id=%s",
             request.state.user_id, kb_id, len(data), strategy_id)
    return ResponseObject(data=data)


@kb_api.get('/{kb_id}/files')
async def list_kb_files(kb_id: int, request: Request):
    """知识库内文件列表（按更新时间倒序，含解析状态与分块数）"""
    data = await file_service.list_kb_files(kb_id, request.state.user_id)
    return ResponseObject(data=data)


@file_api.get('/{file_id}/content')
async def download_kb_file(file_id: int, request: Request):
    """下载文件原内容（流式透传MinIO对象）"""
    stream, file_name, content_type = await file_service.get_file_stream(file_id, request.state.user_id)
    return StreamingResponse(
        stream,
        media_type=content_type or 'application/octet-stream',
        headers={'Content-Disposition': file_service.content_disposition(file_name)},
    )


@file_api.get('/{file_id}/chunks')
async def list_file_chunks(file_id: int, request: Request, page: int = 1, page_size: int = 20):
    """文件分块预览（docstore切分节点，分页；仅解析成功的文件有数据）"""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    data = await file_service.get_file_chunks(file_id, request.state.user_id, page, page_size)
    return ResponseObject(data=data)


@file_api.delete('/{file_id}/delete')
async def delete_kb_file(file_id: int, request: Request):
    """删除知识库文件：清理解析任务(Redis)、MinIO对象、向量分块与kb_files记录"""
    await file_service.delete_kb_file(file_id, request.state.user_id)
    log.info("删除知识库文件: user_id=%s file_id=%s", request.state.user_id, file_id)
    return ResponseObject(message='文件已删除')


@kb_api.post('/{kb_id}/parse-strategies/create')
async def create_parse_strategy(kb_id: int, req: CreateParseStrategyRequest, request: Request):
    """新建文件处理策略（与知识库绑定，策略名知识库内唯一；graph=True须已创建图谱schema）"""
    strategy = await strategy_service.create_parse_strategy(
        kb_id, request.state.user_id, req.name, req.embed_model, req.graph,
        stages=req.stages.model_dump(),
    )
    log.info("新建文件处理策略: user_id=%s kb_id=%s strategy_id=%s name=%s",
             request.state.user_id, kb_id, strategy['id'], strategy['name'])
    return ResponseObject(data=strategy)


@kb_api.get('/{kb_id}/parse-strategies')
async def list_parse_strategies(kb_id: int, request: Request):
    """知识库内文件处理策略列表（按更新时间倒序，含文档引用数）"""
    strategies = await strategy_service.list_parse_strategies(kb_id, request.state.user_id)
    return ResponseObject(data=strategies)


@kb_api.get('/{kb_id}/parse-strategies/{strategy_id}')
async def get_parse_strategy(kb_id: int, strategy_id: int, request: Request):
    """文件处理策略详情"""
    strategy = await strategy_service.get_parse_strategy(kb_id, strategy_id, request.state.user_id)
    return ResponseObject(data=strategy)


@kb_api.patch('/{kb_id}/parse-strategies/{strategy_id}/update')
async def update_parse_strategy(
    kb_id: int, strategy_id: int, req: UpdateParseStrategyRequest, request: Request,
):
    """修改文件处理策略（仅更新提交的字段；图谱schema在「图谱schema」页签维护）"""
    strategy = await strategy_service.update_parse_strategy(
        kb_id, strategy_id, request.state.user_id,
        req.name, req.embed_model, req.graph,
        stages=req.stages.model_dump() if req.stages is not None else None,
    )
    log.info("修改文件处理策略: user_id=%s kb_id=%s strategy_id=%s",
             request.state.user_id, kb_id, strategy_id)
    return ResponseObject(data=strategy)


@kb_api.get('/{kb_id}/graph-schema')
async def get_graph_schema(kb_id: int, request: Request):
    """查询知识库图谱schema（未创建时data为null）"""
    data = await graph_schema_service.get_graph_schema(kb_id, request.state.user_id)
    return ResponseObject(data=data)


@kb_api.put('/{kb_id}/graph-schema')
async def save_graph_schema(kb_id: int, req: SaveGraphSchemaRequest, request: Request):
    """创建/修改知识库图谱schema（整体覆盖保存）"""
    data = await graph_schema_service.save_graph_schema(
        kb_id, request.state.user_id,
        [entity.model_dump() for entity in req.entities],
        [relation.model_dump(by_alias=True) for relation in req.relations],
    )
    log.info("保存知识库图谱schema: user_id=%s kb_id=%s entities=%s relations=%s",
             request.state.user_id, kb_id, len(req.entities), len(req.relations))
    return ResponseObject(data=data)


@kb_api.delete('/{kb_id}/parse-strategies/{strategy_id}/delete')
async def delete_parse_strategy(kb_id: int, strategy_id: int, request: Request):
    """删除文件处理策略"""
    await strategy_service.delete_parse_strategy(kb_id, strategy_id, request.state.user_id)
    log.info("删除文件处理策略: user_id=%s kb_id=%s strategy_id=%s",
             request.state.user_id, kb_id, strategy_id)
    return ResponseObject(data={'id': str(strategy_id)})
