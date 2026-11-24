"""供应商域入参模型"""

from typing import Optional

from pydantic import BaseModel, Field


class ProviderModelSeed(BaseModel):
    """模型目录种子项：测试连接获取的模型写入实例"""

    name: str = Field(min_length=1, max_length=128, description='模型名称（厂商模型 ID）')
    model_type: Optional[str] = Field(default=None, max_length=32, description='模型类型：chat/embedding/rerank...')


class CreateProviderInstanceRequest(BaseModel):
    """新建项目内模型实例"""

    name: str = Field(min_length=1, max_length=64, description='实例名称')
    api_key: Optional[str] = Field(default=None, max_length=512, description='API Key')
    base_url: Optional[str] = Field(default=None, max_length=512, description='API Base URL，缺省使用官方默认地址')
    models: Optional[list[ProviderModelSeed]] = Field(default=None, description='随实例保存的模型目录（测试连接结果）')


class SyncInstanceModelsRequest(BaseModel):
    """同步实例模型目录：按模型名称全量对齐（新增缺失、移除多余，保留已编辑的类型/上下文）"""

    models: list[ProviderModelSeed] = Field(min_length=0, max_length=500, description='模型目录')


class UpdateProviderModelRequest(BaseModel):
    """编辑模型类型与最大上下文长度；未传字段表示不修改，类型传空串/上下文传 null 表示清除"""

    model_type: Optional[str] = Field(default=None, max_length=32, description='模型类型，空串表示清除')
    max_context_length: Optional[int] = Field(default=None, ge=1, le=100_000_000, description='最大上下文长度，null 表示清除')


class TestProviderConnectionRequest(BaseModel):
    """测试模型实例连接：初次添加实例时数据库尚无记录，不校验提供商/实例存在性

    api_key/base_url 缺省时回退到已保存实例配置（如有），再回退到预置厂商默认地址。
    """

    provider_name: str = Field(min_length=1, max_length=64, description='提供商名称，用于匹配预置目录与鉴权协议')
    instance_id: Optional[int] = Field(default=None, ge=1, description='已保存的模型实例 ID，草稿实例可不传')
    api_key: Optional[str] = Field(default=None, max_length=512, description='临时测试用 API Key')
    base_url: Optional[str] = Field(default=None, max_length=512, description='临时测试用 API Base URL')


class UpdateProviderInstanceRequest(BaseModel):
    """保存项目内模型实例连接配置：字段缺省表示不修改"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=64, description='实例名称')
    api_key: Optional[str] = Field(default=None, max_length=512, description='API Key，空串表示清除已配置的 Key')
    base_url: Optional[str] = Field(default=None, max_length=512, description='API Base URL，空串表示使用官方默认地址')
    enabled: Optional[bool] = Field(default=None, description='是否在项目内启用')
