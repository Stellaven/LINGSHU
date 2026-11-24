"""供应商域业务逻辑（项目内模型提供商目录、模型实例配置管理）

权限规则：项目须存在且当前用户为项目成员（查看/配置均需成员身份）。
"""

from typing import Optional

from core.exceptions import BusinessError
from modules.provider import model_client, repository
from modules.provider.constants import (
    CODE_PROVIDER_CONFIG_INCOMPLETE,
    CODE_PROVIDER_CONNECTION_FAILED,
    find_provider_catalog,
)
from modules.team import repository as team_repository
from modules.team.constants import CODE_NOT_PROJECT_MEMBER, CODE_PROJECT_NOT_FOUND


async def _require_project_member(project_id: int, user_id: int) -> None:
    """项目须存在且当前用户须为项目成员，否则抛业务异常"""
    if not await team_repository.project_exists(project_id):
        raise BusinessError('项目不存在', code=CODE_PROJECT_NOT_FOUND, status_code=404)
    if not await team_repository.is_project_member(project_id, user_id):
        raise BusinessError('尚不是项目成员', code=CODE_NOT_PROJECT_MEMBER, status_code=403)


async def list_providers(project_id: int, user_id: int) -> list[dict]:
    """项目内模型提供商目录（含该项目的模型实例列表）"""
    await _require_project_member(project_id, user_id)
    return await repository.list_providers(project_id)


async def list_embedding_models(project_id: int, user_id: int) -> list[dict]:
    """项目内可选嵌入模型列表（用于新建知识库时选择向量模型）"""
    await _require_project_member(project_id, user_id)
    return await repository.list_embedding_models(project_id)


async def list_chat_models(project_id: int, user_id: int) -> list[dict]:
    """项目内可选LLM列表（用于文件处理策略数据提取器选择模型）"""
    await _require_project_member(project_id, user_id)
    return await repository.list_chat_models(project_id)


async def test_connection(
    project_id: int, user_id: int, provider_id: int, provider_name: str,
    instance_id: Optional[int], api_key: Optional[str], base_url: Optional[str],
) -> dict:
    """测试模型连接并返回厂商模型目录

    不校验提供商/实例是否已入库（初次添加实例时数据库尚无记录）。
    连接配置优先级：本次表单传入 -> 已保存实例配置 -> 预置厂商默认地址。
    提供商元数据优先取数据库，取不到则回退到预置目录。
    """
    await _require_project_member(project_id, user_id)
    provider, instance = await repository.get_provider_and_instance(
        project_id, provider_id, instance_id,
    )

    provider_title = provider.name if provider else provider_name.strip()
    if not provider_title:
        raise BusinessError(
            '缺少提供商信息', code=CODE_PROVIDER_CONFIG_INCOMPLETE, status_code=400)

    resolved_key = (api_key or '').strip()
    if not resolved_key and instance:
        resolved_key = instance.api_key or ''
    resolved_base = (base_url or '').strip()
    if not resolved_base and instance:
        resolved_base = instance.base_url or ''
    if not resolved_base and provider:
        resolved_base = provider.default_base_url or ''
    if not resolved_base:
        catalog_entry = find_provider_catalog(provider_title)
        resolved_base = catalog_entry[3] if catalog_entry else ''

    if not resolved_base:
        raise BusinessError(
            '请填写 API Base URL', code=CODE_PROVIDER_CONFIG_INCOMPLETE, status_code=400)
    # Ollama 本地服务通常无需鉴权，其余厂商缺少 Key 时直接提示，避免无效外呼
    if not resolved_key and provider_title != 'Ollama':
        raise BusinessError(
            '请先填写 API Key', code=CODE_PROVIDER_CONFIG_INCOMPLETE, status_code=400)

    try:
        models = await model_client.fetch_models(provider_title, resolved_base, resolved_key)
    except model_client.ProviderConnectionError as exc:
        raise BusinessError(
            str(exc), code=CODE_PROVIDER_CONNECTION_FAILED, status_code=502) from exc

    return {
        'provider': provider_title,
        'baseUrl': resolved_base,
        'models': models,
        'total': len(models),
    }


def _model_seeds(models) -> list[tuple[str, Optional[str]]]:
    """将模型种子入参转为 [(name, model_type)]，去重并截断空白"""
    seeds: list[tuple[str, Optional[str]]] = []
    seen: set[str] = set()
    for item in models or []:
        name = (item.name or '').strip()
        if not name or name in seen:
            continue
        seen.add(name)
        seeds.append((name, (item.model_type or '').strip() or None))
    return seeds


async def create_instance(
    project_id: int, user_id: int, provider_id: int,
    name: str, api_key: Optional[str], base_url: Optional[str],
    models=None,
) -> dict:
    """为项目内提供商新建模型实例（可携带测试连接获取的模型目录一并落库）"""
    await _require_project_member(project_id, user_id)
    instance = await repository.create_instance(
        project_id, provider_id, name,
        None if api_key is None else api_key.strip(),
        None if base_url is None else base_url.strip(),
        _model_seeds(models),
    )
    if not instance:
        raise BusinessError('模型提供商不存在', code=CODE_PROVIDER_NOT_FOUND, status_code=404)
    return instance


async def sync_instance_models(
    project_id: int, user_id: int, provider_id: int, instance_id: int, models,
) -> dict:
    """同步实例模型目录（测试连接成功后调用，按名称全量对齐）"""
    await _require_project_member(project_id, user_id)
    instance = await repository.get_instance(project_id, provider_id, instance_id)
    if not instance:
        raise BusinessError('模型实例不存在', code=CODE_INSTANCE_NOT_FOUND, status_code=404)
    synced = await repository.sync_instance_models(instance_id, _model_seeds(models))
    return {'id': str(instance.id), 'models': synced}


async def update_model(
    project_id: int, user_id: int, provider_id: int, instance_id: int, model_id: int,
    model_type: Optional[str], max_context_length: Optional[int], context_provided: bool,
) -> dict:
    """编辑模型类型与最大上下文长度"""
    await _require_project_member(project_id, user_id)
    model = await repository.update_model(
        project_id, provider_id, instance_id, model_id,
        model_type, max_context_length, context_provided,
    )
    if not model:
        raise BusinessError('模型不存在', code=40409, status_code=404)
    return model


async def update_instance(
    project_id: int, user_id: int, provider_id: int, instance_id: int,
    name: Optional[str], api_key: Optional[str], base_url: Optional[str],
    enabled: Optional[bool],
) -> dict:
    """保存项目内模型实例的连接配置"""
    await _require_project_member(project_id, user_id)
    instance = await repository.update_instance(
        project_id, provider_id, instance_id,
        None if name is None else name.strip(),
        None if api_key is None else api_key.strip(),
        None if base_url is None else base_url.strip(),
        enabled,
    )
    if not instance:
        raise BusinessError('模型实例不存在', code=CODE_INSTANCE_NOT_FOUND, status_code=404)
    return instance


async def delete_instance(
    project_id: int, user_id: int, provider_id: int, instance_id: int,
) -> None:
    """删除项目内模型实例"""
    await _require_project_member(project_id, user_id)
    deleted = await repository.delete_instance(project_id, provider_id, instance_id)
    if not deleted:
        raise BusinessError('模型实例不存在', code=CODE_INSTANCE_NOT_FOUND, status_code=404)
