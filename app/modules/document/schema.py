"""文档域入参/出参模型，随上传、解析、分片接口完善补充"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ParserType = Literal['Docling', 'MonkeyOCRv2']
ChunkerType = Literal[
    'semantic', 'sentence', 'token', 'sentence_window', 'hierarchical',
    'markdown', 'html', 'json', 'code', 'simple_file',
]


class StageExtractor(BaseModel):
    """编排序列中的提取器节点（每个实例独立指定执行LLM，空串表示该提取器跳过；

    params 为提取器参数配置，未提供的键按后端默认值初始化）
    """
    id: Literal['title', 'summary', 'question', 'keyword', 'entity']
    llm: str = Field(default='', max_length=128)
    params: dict[str, Any] = Field(default_factory=dict)


class SplitStageEntry(BaseModel):
    """编排序列中的分块器节点（params 为分块器参数，未提供的键按后端默认值初始化）"""
    id: ChunkerType
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='before')
    @classmethod
    def _accept_plain_id(cls, value: Any) -> Any:
        # 兼容历史数据：split 中的纯字符串 id 等价于「默认参数」
        if isinstance(value, str):
            return {'id': value, 'params': {}}
        return value


class StrategyStages(BaseModel):
    """策略编排序列：解析 → 前置(文档级)提取 → 分块(可级联) → 后置(块级)提取

    parser 至多1个（重复添加时前端自动替换），split 至少1个（保存时校验）。
    """
    parser: list[ParserType] = Field(default_factory=list)
    pre_extract: list[StageExtractor] = Field(default_factory=list)
    split: list[SplitStageEntry] = Field(default_factory=list)
    post_extract: list[StageExtractor] = Field(default_factory=list)


class GraphSchemaEntity(BaseModel):
    """图谱schema实体类型：name/desc + 属性字段（属性名→属性描述）"""
    name: str = Field(min_length=1, max_length=64, description='实体类型名')
    desc: str = Field(default='', max_length=256, description='实体类型描述')
    properties: dict[str, str] = Field(
        default_factory=dict, description='属性字段（属性名→属性描述）')


class GraphSchemaRelation(BaseModel):
    """图谱schema关系类型：subject/object 须指向entities中的实体类型"""
    name: str = Field(min_length=1, max_length=64, description='关系类型名')
    desc: str = Field(default='', max_length=256, description='关系类型描述')
    subject_type: str = Field(min_length=1, max_length=64, alias='subjectType',
                              description='起点（主体）实体类型名')
    object_type: str = Field(min_length=1, max_length=64, alias='objectType',
                             description='终点（客体）实体类型名')

    model_config = ConfigDict(populate_by_name=True)


class GraphSchemaDef(BaseModel):
    """图谱schema定义（知识库维度，每库一份）：构图抽取的实体/关系对齐依据"""
    entities: list[GraphSchemaEntity] = Field(default_factory=list, description='实体类型定义')
    relations: list[GraphSchemaRelation] = Field(default_factory=list, description='关系类型定义')


class SaveGraphSchemaRequest(BaseModel):
    """创建/修改知识库图谱schema（整体覆盖保存）"""
    entities: list[GraphSchemaEntity] = Field(default_factory=list)
    relations: list[GraphSchemaRelation] = Field(default_factory=list)


class CreateParseStrategyRequest(BaseModel):
    """新建文件处理策略（知识库维度；graph=True 要求知识库已创建图谱schema）"""
    name: str = Field(min_length=1, max_length=64, description='策略名称（知识库内唯一）')
    embed_model: str = Field(min_length=1, max_length=128, description='嵌入模型名')
    # 编排序列：解析 → 前置提取 → 分块 → 后置提取
    stages: StrategyStages
    graph: bool = True

    model_config = ConfigDict(populate_by_name=True)


class UpdateParseStrategyRequest(BaseModel):
    """修改文件处理策略（全字段可选，仅提交需要变更的项；图谱schema在「图谱schema」页签维护）"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    embed_model: Optional[str] = Field(default=None, min_length=1, max_length=128)
    stages: Optional[StrategyStages] = None
    graph: Optional[bool] = None

    model_config = ConfigDict(populate_by_name=True)
