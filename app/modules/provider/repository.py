"""供应商域数据访问层：项目内模型提供商目录/模型实例配置读写

出参统一序列化为前端契约（camelCase + 字符串id），见 web/src/types/models.ts。
实例（model_instances）按项目隔离：同一项目内同一提供商可创建多个实例。
"""

from typing import Optional

from sqlalchemy import delete, func, select

from core.dependencies import get_db_session
from db.pg.orm_models import Model, ModelInstance, ModelProvider


def _model_to_dict(model: Model) -> dict:
    """模型目录项：类型/上下文长度未填写时为 None（前端不展示）"""
    return {
        'id': str(model.id),
        'name': model.name,
        'modelType': model.model_type,
        'maxContextLength': model.max_context_length,
    }


def _instance_to_dict(instance: ModelInstance, models: Optional[list[Model]] = None) -> dict:
    """模型实例：API Key 仅回传是否已配置标记，不回传明文"""
    return {
        'id': str(instance.id),
        'name': instance.name,
        'baseUrl': instance.base_url or '',
        'apiKeyConfigured': bool(instance.api_key),
        'enabled': bool(instance.enabled),
        'models': [_model_to_dict(model) for model in (models or [])],
    }


def _provider_to_dict(
    provider: ModelProvider,
    instances: list[ModelInstance],
    models_by_instance: Optional[dict[int, list[Model]]] = None,
) -> dict:
    """提供商目录项：聚合该项目下该提供商的全部模型实例"""
    model_map = models_by_instance or {}
    return {
        'id': str(provider.id),
        'name': provider.name,
        'region': provider.region,
        'color': provider.color,
        'logo': provider.logo or '',
        'defaultBaseUrl': provider.default_base_url or '',
        # 任一实例配置了 API Key 即视为该提供商已正常配置（前端状态点转绿）
        'apiKeyConfigured': any(bool(inst.api_key) for inst in instances),
        'instances': [
            _instance_to_dict(inst, model_map.get(inst.id, [])) for inst in instances
        ],
    }


async def list_providers(project_id: int) -> list[dict]:
    """项目内模型提供商目录（按预置排序），聚合并返回该项目各提供商的模型实例与模型目录"""
    async with get_db_session() as session:
        providers = (await session.execute(
            select(ModelProvider).order_by(ModelProvider.sort_order, ModelProvider.id)
        )).scalars().all()
        instances = (await session.execute(
            select(ModelInstance)
            .where(ModelInstance.project_id == project_id)
            .order_by(ModelInstance.id)
        )).scalars().all()
        instance_ids = [inst.id for inst in instances]
        models: list[Model] = []
        if instance_ids:
            models = list((await session.execute(
                select(Model)
                .where(Model.instance_id.in_(instance_ids))
                .order_by(Model.id)
            )).scalars().all())

    by_provider: dict[int, list[ModelInstance]] = {}
    for inst in instances:
        by_provider.setdefault(inst.provider_id, []).append(inst)
    models_by_instance: dict[int, list[Model]] = {}
    for model in models:
        models_by_instance.setdefault(model.instance_id, []).append(model)

    return [
        _provider_to_dict(p, by_provider.get(p.id, []), models_by_instance) for p in providers
    ]


async def get_provider_and_instance(
    project_id: int, provider_id: int, instance_id: Optional[int],
) -> tuple[Optional[ModelProvider], Optional[ModelInstance]]:
    """读取项目内提供商与指定实例；instance_id 为空时只返回提供商"""
    async with get_db_session() as session:
        provider = await session.get(ModelProvider, provider_id)
        if not provider:
            return None, None
        if instance_id is None:
            return provider, None
        instance = (await session.execute(
            select(ModelInstance).where(
                ModelInstance.id == instance_id,
                ModelInstance.project_id == project_id,
                ModelInstance.provider_id == provider_id,
            )
        )).scalars().first()
        return provider, instance


async def list_embedding_models(project_id: int) -> list[dict]:
    """项目内可选嵌入模型：实例下的 embedding 类型模型，展示为「实例名/模型名」"""
    async with get_db_session() as session:
        rows = (await session.execute(
            select(Model, ModelInstance, ModelProvider)
            .join(ModelInstance, Model.instance_id == ModelInstance.id)
            .join(ModelProvider, ModelInstance.provider_id == ModelProvider.id)
            .where(
                ModelInstance.project_id == project_id,
                func.lower(Model.model_type) == 'embedding',
            )
            .order_by(
                ModelProvider.sort_order, ModelProvider.id,
                ModelInstance.id, Model.id,
            )
        )).all()

    return [
        {
            'id': str(model.id),
            'name': model.name,
            # 前端下拉框展示文案：实例名/嵌入模型
            'label': f'{instance.name}/{model.name}',
            'instanceId': str(instance.id),
            'instanceName': instance.name,
            'providerId': str(provider.id),
            'providerName': provider.name,
        }
        for model, instance, provider in rows
    ]


async def list_chat_models(project_id: int) -> list[dict]:
    """项目内可选LLM：实例下的 chat 类型模型，展示为「实例名/模型名」（数据提取器选择用）"""
    async with get_db_session() as session:
        rows = (await session.execute(
            select(Model, ModelInstance, ModelProvider)
            .join(ModelInstance, Model.instance_id == ModelInstance.id)
            .join(ModelProvider, ModelInstance.provider_id == ModelProvider.id)
            .where(
                ModelInstance.project_id == project_id,
                func.lower(Model.model_type) == 'chat',
            )
            .order_by(
                ModelProvider.sort_order, ModelProvider.id,
                ModelInstance.id, Model.id,
            )
        )).all()

    return [
        {
            'id': str(model.id),
            'name': model.name,
            # 前端下拉框展示文案：实例名/LLM
            'label': f'{instance.name}/{model.name}',
            'instanceId': str(instance.id),
            'instanceName': instance.name,
            'providerId': str(provider.id),
            'providerName': provider.name,
        }
        for model, instance, provider in rows
    ]


async def create_instance(
    project_id: int, provider_id: int, name: str,
    api_key: Optional[str], base_url: Optional[str],
    models: Optional[list[tuple[str, Optional[str]]]] = None,
) -> Optional[dict]:
    """为项目内某提供商新建模型实例；提供商不存在时返回 None

    models 为测试连接获取的目录 [(name, model_type)]，随实例一并落库。
    """
    async with get_db_session() as session:
        provider = await session.get(ModelProvider, provider_id)
        if not provider:
            return None
        instance = ModelInstance(
            project_id=project_id, provider_id=provider_id, name=name,
            # api_key/base_url 列为 NOT NULL，未配置时落空串
            api_key=api_key or '', base_url=base_url or '', enabled=False,
        )
        session.add(instance)
        await session.flush()
        if models:
            await _seed_models(session, instance.id, models)
        await session.refresh(instance)
        instance_models = (await session.execute(
            select(Model).where(Model.instance_id == instance.id).order_by(Model.id)
        )).scalars().all()
        return _instance_to_dict(instance, list(instance_models))


async def _seed_models(
    session, instance_id: int, models: list[tuple[str, Optional[str]]],
) -> None:
    """按名称幂等写入模型目录：已存在的跳过（保留已编辑的类型/上下文）"""
    existing = {
        name for name in (await session.execute(
            select(Model.name).where(Model.instance_id == instance_id)
        )).scalars().all()
    }
    for name, model_type in models:
        if name in existing:
            continue
        session.add(Model(instance_id=instance_id, name=name, model_type=model_type))
    await session.flush()


async def get_instance(
    project_id: int, provider_id: int, instance_id: int,
) -> Optional[ModelInstance]:
    """读取项目内指定提供商下的模型实例"""
    async with get_db_session() as session:
        return (await session.execute(
            select(ModelInstance).where(
                ModelInstance.id == instance_id,
                ModelInstance.project_id == project_id,
                ModelInstance.provider_id == provider_id,
            )
        )).scalars().first()


async def sync_instance_models(
    instance_id: int, models: list[tuple[str, Optional[str]]],
) -> list[dict]:
    """同步实例模型目录：按名称全量对齐（新增缺失、移除多余，保留已编辑的类型/上下文）"""
    async with get_db_session() as session:
        existing_by_name: dict[str, Model] = {
            model.name: model for model in (await session.execute(
                select(Model).where(Model.instance_id == instance_id)
            )).scalars().all()
        }
        incoming_names = {name for name, _ in models}

        # 移除目录中已不存在的模型
        for name, model in existing_by_name.items():
            if name not in incoming_names:
                await session.delete(model)

        # 新增目录中出现的模型
        for name, model_type in models:
            if name not in existing_by_name:
                session.add(Model(instance_id=instance_id, name=name, model_type=model_type))
        await session.flush()

        rows = (await session.execute(
            select(Model).where(Model.instance_id == instance_id).order_by(Model.id)
        )).scalars().all()
        return [_model_to_dict(model) for model in rows]


async def update_model(
    project_id: int, provider_id: int, instance_id: int, model_id: int,
    model_type: Optional[str], max_context_length: Optional[int],
    context_provided: bool = False,
) -> Optional[dict]:
    """编辑模型类型与最大上下文长度

    model_type 为 None 表示不修改，空串表示清除；
    context_provided=False 表示上下文长度不修改，True 时按 max_context_length（可为 None）设置。
    返回更新后的模型；模型不存在或不属于该实例时返回 None。
    """
    async with get_db_session() as session:
        model = (await session.execute(
            select(Model)
            .join(ModelInstance, Model.instance_id == ModelInstance.id)
            .where(
                Model.id == model_id,
                Model.instance_id == instance_id,
                ModelInstance.project_id == project_id,
                ModelInstance.provider_id == provider_id,
            )
        )).scalars().first()
        if not model:
            return None

        if model_type is not None:
            model.model_type = model_type.strip() or None
        if context_provided:
            model.max_context_length = max_context_length

        await session.flush()
        await session.refresh(model)
        return _model_to_dict(model)


async def update_instance(
    project_id: int, provider_id: int, instance_id: int,
    name: Optional[str], api_key: Optional[str], base_url: Optional[str],
    enabled: Optional[bool],
) -> Optional[dict]:
    """更新项目内指定实例：入参为 None 表示不修改该字段；api_key 传空串表示清除"""
    async with get_db_session() as session:
        instance = (await session.execute(
            select(ModelInstance).where(
                ModelInstance.id == instance_id,
                ModelInstance.project_id == project_id,
                ModelInstance.provider_id == provider_id,
            )
        )).scalars().first()
        if not instance:
            return None

        if name is not None:
            instance.name = name
        if api_key is not None:
            instance.api_key = api_key
        if base_url is not None:
            instance.base_url = base_url
        if enabled is not None:
            instance.enabled = enabled

        await session.flush()
        await session.refresh(instance)
        return _instance_to_dict(instance)


async def delete_instance(project_id: int, provider_id: int, instance_id: int) -> bool:
    """删除项目内指定实例（连同其模型配置）；实例不存在时返回 False"""
    async with get_db_session() as session:
        instance = (await session.execute(
            select(ModelInstance).where(
                ModelInstance.id == instance_id,
                ModelInstance.project_id == project_id,
                ModelInstance.provider_id == provider_id,
            )
        )).scalars().first()
        if not instance:
            return False

        # 先清理实例下的模型配置，避免外键约束阻止删除
        await session.execute(delete(Model).where(Model.instance_id == instance_id))
        await session.delete(instance)
        return True
