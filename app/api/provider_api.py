"""项目内模型配置接口：提供商目录查询、可选嵌入模型查询、连接测试、模型实例的新增/保存/删除

模型配置按项目隔离：模型实例（model_instances）关联项目与提供商，同一提供商可有多个实例。
"""

import logging

from fastapi import APIRouter, Request

from common.response import ResponseObject
from modules.provider import service
from modules.provider.schema import (
    CreateProviderInstanceRequest,
    SyncInstanceModelsRequest,
    TestProviderConnectionRequest,
    UpdateProviderInstanceRequest,
    UpdateProviderModelRequest,
)

# 项目维度资源路由（前端契约：/api/projects/{projectId}/providers/...）
api = APIRouter(prefix="/projects")

log = logging.getLogger(__name__)


@api.get('/{project_id}/providers/list')
async def list_providers(project_id: int, request: Request):
    """项目内模型提供商目录（含该项目的模型实例列表，按预置排序返回）"""
    providers = await service.list_providers(project_id, request.state.user_id)
    return ResponseObject(data=providers)


@api.get('/{project_id}/providers/embedding-models')
async def list_embedding_models(project_id: int, request: Request):
    """项目内可选嵌入模型（实例下的 embedding 模型，展示为「实例名/模型名」）"""
    models = await service.list_embedding_models(project_id, request.state.user_id)
    return ResponseObject(data=models)


@api.get('/{project_id}/providers/chat-models')
async def list_chat_models(project_id: int, request: Request):
    """项目内可选LLM（实例下的 chat 模型，展示为「实例名/模型名」；数据提取器选择用）"""
    models = await service.list_chat_models(project_id, request.state.user_id)
    return ResponseObject(data=models)


@api.post('/{project_id}/providers/{provider_id}/test-connection')
async def test_connection(
    project_id: int, provider_id: int,
    req: TestProviderConnectionRequest, request: Request,
):
    """测试模型连接并获取厂商模型列表（不校验提供商/实例存在性，支持初次添加实例时调用）"""
    result = await service.test_connection(
        project_id, request.state.user_id, provider_id, req.provider_name,
        req.instance_id, req.api_key, req.base_url,
    )
    log.info("测试模型连接: user_id=%s project_id=%s provider_id=%s provider=%s instance_id=%s models=%s",
             request.state.user_id, project_id, provider_id, req.provider_name,
             req.instance_id, result['total'])
    return ResponseObject(data=result)


@api.post('/{project_id}/providers/{provider_id}/instances')
async def create_instance(
    project_id: int, provider_id: int, req: CreateProviderInstanceRequest, request: Request,
):
    """新建项目内模型实例（可携带测试连接获取的模型目录）"""
    instance = await service.create_instance(
        project_id, request.state.user_id, provider_id,
        req.name, req.api_key, req.base_url, req.models,
    )
    log.info("新建项目模型实例: user_id=%s project_id=%s provider_id=%s name=%s",
             request.state.user_id, project_id, provider_id, req.name)
    return ResponseObject(data=instance)


@api.put('/{project_id}/providers/{provider_id}/instances/{instance_id}/models')
async def sync_instance_models(
    project_id: int, provider_id: int, instance_id: int,
    req: SyncInstanceModelsRequest, request: Request,
):
    """同步实例模型目录（测试连接成功后调用，按名称全量对齐）"""
    result = await service.sync_instance_models(
        project_id, request.state.user_id, provider_id, instance_id, req.models,
    )
    log.info("同步实例模型目录: user_id=%s project_id=%s instance_id=%s models=%s",
             request.state.user_id, project_id, instance_id, len(result['models']))
    return ResponseObject(data=result)


@api.patch('/{project_id}/providers/{provider_id}/instances/{instance_id}/models/{model_id}')
async def update_model(
    project_id: int, provider_id: int, instance_id: int, model_id: int,
    req: UpdateProviderModelRequest, request: Request,
):
    """编辑模型类型与最大上下文长度"""
    context_provided = 'max_context_length' in req.model_fields_set
    model = await service.update_model(
        project_id, request.state.user_id, provider_id, instance_id, model_id,
        req.model_type, req.max_context_length, context_provided,
    )
    log.info("编辑模型配置: user_id=%s project_id=%s instance_id=%s model_id=%s",
             request.state.user_id, project_id, instance_id, model_id)
    return ResponseObject(data=model)


@api.patch('/{project_id}/providers/{provider_id}/instances/{instance_id}/update')
async def update_instance(
    project_id: int, provider_id: int, instance_id: int,
    req: UpdateProviderInstanceRequest, request: Request,
):
    """保存项目内模型实例连接配置"""
    instance = await service.update_instance(
        project_id, request.state.user_id, provider_id, instance_id,
        req.name, req.api_key, req.base_url, req.enabled,
    )
    log.info("保存项目模型实例配置: user_id=%s project_id=%s provider_id=%s instance_id=%s",
             request.state.user_id, project_id, provider_id, instance_id)
    return ResponseObject(data=instance)


@api.delete('/{project_id}/providers/{provider_id}/instances/{instance_id}/delete')
async def delete_instance(project_id: int, provider_id: int, instance_id: int, request: Request):
    """删除项目内模型实例"""
    await service.delete_instance(
        project_id, request.state.user_id, provider_id, instance_id,
    )
    log.info("删除项目模型实例: user_id=%s project_id=%s provider_id=%s instance_id=%s",
             request.state.user_id, project_id, provider_id, instance_id)
    return ResponseObject(data={'id': str(instance_id)})
