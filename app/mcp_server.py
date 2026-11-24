"""MCP服务：把知识库检索能力以 MCP 工具形式提供给外部 Agent

- 传输：Streamable HTTP（stateless + json_response，无会话管理），挂载于主应用
  /mcp（POST http://<host>/mcp），外部Agent（Claude/Cursor/Dify等）可直接接入
- 工具：search_knowledge —— 复用 modules/retriever/service.retrieval 全链路
  （ES/向量/图谱三路召回 + RRF融合 + rerank），返回 JSON 文本
- 鉴权：/mcp 在 AuthMiddleware 白名单中开放；如需收紧可在 MCPServer 上挂
  token_verifier（auth_server_provider/token_verifier 参数）
"""

import json
import logging

from mcp.server.mcpserver import MCPServer

from modules.retriever import service as retrieve_service
from modules.retriever.schema import RetrievalRequest

log = logging.getLogger(__name__)

mcp = MCPServer(
    name='lingshu-knowledge-retrieval',
    instructions=(
        '灵枢知识库检索服务。调用 search_knowledge 工具可在指定知识库中检索与问题'
        '相关的文档片段与图谱知识（三路召回+重排），返回片段列表（含来源文件与相关性分数）。'
        'dataset_ids 为知识库ID列表（字符串形式的数字ID）。'
    ),
)


@mcp.tool(
    title='知识库检索',
    description=(
        '在指定知识库中检索与问题相关的内容。返回JSON：{total, page, page_size, chunks: '
        '[{id, content, file_key, score, recall_source, metadata}]}，chunks按相关性降序。'
        'recall_source 标记召回来源（es=全文检索/vector=语义向量/graph=知识图谱）。'
    ),
)
async def search_knowledge(
    question: str,
    dataset_ids: list[str],
    top_k: int = 10,
    page: int = 1,
    enable_graph_recall: bool = True,
    meta_data_filter: dict | None = None,
) -> str:
    """检索知识库，返回相关片段列表

    Args:
        question: 检索问题
        dataset_ids: 知识库ID列表（如 ["1", "3"]）
        top_k: 返回条数
        page: 页码（从1开始）
        enable_graph_recall: 是否启用知识图谱召回
        meta_data_filter: 元数据过滤，如 {"file_key": "报告.pdf"} 或
            {"tags": ["A"], "score": {"op": "gt", "value": 3}}
    """
    request = RetrievalRequest(
        question=question,
        dataset_ids=dataset_ids,
        page=page,
        page_size=top_k,
        enable_graph_recall=enable_graph_recall,
        meta_data_filter=meta_data_filter or {},
    )
    data = await retrieve_service.retrieval(request)
    return json.dumps(data, ensure_ascii=False)


# stateless：每次请求独立处理，适配外部Agent的HTTP直连调用方式。
# 内部路由保持默认 /mcp，由 main.py 挂载到根路径（app.mount('', mcp_app)），
# 使端点精确为 POST /mcp（避免 mount('/mcp') 产生的 307 重定向）。
# host=0.0.0.0：避免默认 127.0.0.1 自动开启 DNS rebinding 保护（只放行 localhost 请求头）
mcp_app = mcp.streamable_http_app(stateless_http=True, json_response=True, host='0.0.0.0')


_session_cm = None


async def start_session_manager() -> None:
    """初始化 MCP 会话管理器（挂载子应用的 lifespan 不会自动执行，须在主应用启动时调用）"""
    global _session_cm
    _session_cm = mcp.session_manager.run()
    await _session_cm.__aenter__()


async def stop_session_manager() -> None:
    """关闭 MCP 会话管理器（主应用关闭时调用）"""
    global _session_cm
    if _session_cm:
        await _session_cm.__aexit__(None, None, None)
        _session_cm = None
