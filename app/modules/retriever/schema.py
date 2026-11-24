from typing import Optional, Any

from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    """检索请求入参

    meta_data_filter 结构（三路召回共用的前置过滤条件）：
    {"file_key": "a.txt"}                          # 等值过滤
    {"tags": ["x", "y"]}                           # 集合过滤
    {"score": {"op": "gt", "value": 3}}            # 显式操作符：eq/in/gt/gte/lt/lte/contains
    字段为 chunk 元数据键；file_key 为文件名（特殊字段），其余按 metadata.<field> 处理。
    """
    dataset_ids: list[str] = Field(..., description="知识库ID列表")
    question: str = Field(..., min_length=1, description="查询问题")
    page: int = Field(default=1, ge=1, description="页码，从1开始")
    page_size: int = Field(default=10, ge=1, description="页大小")
    similarity_threshold: float = Field(default=0.2, ge=0.0, le=1.0, description="相似度阈值（rerank相关性分）")
    keywords_similarity_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="关键词相似度权重（保留字段，RRF融合暂不使用）")
    rerank_candidates_count: int = Field(default=64, ge=1, description="送入重排的候选数量")
    meta_data_filter: dict[str, Any] = Field(default_factory=dict, description="元数据过滤条件（三路召回前置过滤）")
    enable_graph_recall: bool = Field(default=True, description="是否启用KAG知识图谱召回")
    graph_recall_topk: int = Field(default=5, ge=1, description="图谱召回条数")
