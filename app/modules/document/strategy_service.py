"""文件处理策略业务层：知识库维度策略的增删改查

权限：仅知识库所属项目的成员可操作（复用团队域成员校验）。
"""

from typing import Optional

from core.exceptions import BusinessError
from modules.document import graph_schema_repository, strategy_repository
from modules.team import repository as team_repository
from modules.team.constants import (
    CODE_NOT_PROJECT_MEMBER,
    CODE_PROJECT_KB_NAME_CONFLICT,
    CODE_PROJECT_KB_NOT_FOUND,
)

CODE_STRATEGY_NOT_FOUND = 40408  # 策略不存在（HTTP 404）
CODE_STRATEGY_NAME_CONFLICT = 40903  # 知识库内策略名已存在（HTTP 409）


def _apply_stages(stages: dict) -> dict:
    """校验并归一化编排序列（至少含解析器与分块器）

    split 条目兼容历史纯字符串 id，统一归一化为 {id, params}；
    提取器条目归一化补齐 params（历史数据无该键，等价于默认参数）。
    """
    split = []
    for entry in stages.get('split') or []:
        if isinstance(entry, str):
            entry = {'id': entry, 'params': {}}
        elif isinstance(entry, dict):
            entry = {'id': entry.get('id'), 'params': dict(entry.get('params') or {})}
        else:
            raise BusinessError('分块器配置格式不正确', code=40010, status_code=400)
        if not entry['id']:
            raise BusinessError('分块器配置缺少 id', code=40010, status_code=400)
        split.append(entry)

    def _normalize_extractors(entries) -> list:
        out = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                raise BusinessError('提取器配置格式不正确', code=40010, status_code=400)
            out.append({
                'id': entry.get('id'),
                'llm': entry.get('llm') or '',
                'params': dict(entry.get('params') or {}),
            })
        return out

    stages = {
        'parser': list(stages.get('parser') or []),
        'pre_extract': _normalize_extractors(stages.get('pre_extract')),
        'split': split,
        'post_extract': _normalize_extractors(stages.get('post_extract')),
    }
    if not stages['parser']:
        raise BusinessError('缺少解析器：编排流程至少需要一个解析步骤', code=40010, status_code=400)
    if not stages['split']:
        raise BusinessError('缺少分块器：请至少添加一个分块器', code=40010, status_code=400)
    return stages


async def _require_kb_member(kb_id: int, user_id: int) -> dict:
    """知识库须存在且当前用户须为其所属项目的成员，返回知识库归属信息"""
    kb = await strategy_repository.get_knowledge_base(kb_id)
    if not kb:
        raise BusinessError('知识库不存在', code=CODE_PROJECT_KB_NOT_FOUND, status_code=404)
    if not await team_repository.is_project_member(kb['projectId'], user_id):
        raise BusinessError('尚不是项目成员', code=CODE_NOT_PROJECT_MEMBER, status_code=403)
    return kb


async def _require_graph_schema(kb_id: int) -> None:
    """开启构建图谱的策略要求知识库已创建图谱schema（schema在「图谱schema」页签维护）"""
    if not await graph_schema_repository.schema_exists(kb_id):
        raise BusinessError(
            '开启构建图谱前请先在「图谱schema」页签创建图谱schema', code=40010, status_code=400)


async def create_parse_strategy(
    kb_id: int, user_id: int, name: str, embed_model: str, graph: bool, stages: dict,
) -> dict:
    """新建文件处理策略（策略名知识库内唯一；graph=True须已创建图谱schema）"""
    await _require_kb_member(kb_id, user_id)
    name = (name or '').strip()
    if not name:
        raise BusinessError('请输入策略名称', code=40010, status_code=400)
    if await strategy_repository.strategy_name_exists(kb_id, name):
        raise BusinessError('该知识库下已存在同名策略',
                            code=CODE_STRATEGY_NAME_CONFLICT, status_code=409)
    stages = _apply_stages(stages)
    if graph:
        await _require_graph_schema(kb_id)
    return await strategy_repository.create_strategy(
        kb_id, name, embed_model, graph, stages)


async def list_parse_strategies(kb_id: int, user_id: int) -> list[dict]:
    """知识库内策略列表"""
    await _require_kb_member(kb_id, user_id)
    return await strategy_repository.list_strategies(kb_id)


async def get_parse_strategy(kb_id: int, strategy_id: int, user_id: int) -> dict:
    """策略详情"""
    await _require_kb_member(kb_id, user_id)
    strategy = await strategy_repository.get_strategy(kb_id, strategy_id)
    if not strategy:
        raise BusinessError('策略不存在', code=CODE_STRATEGY_NOT_FOUND, status_code=404)
    return strategy


async def update_parse_strategy(
    kb_id: int, strategy_id: int, user_id: int,
    name: Optional[str], embed_model: Optional[str],
    graph: Optional[bool], stages: Optional[dict] = None,
) -> dict:
    """修改策略（仅更新提交的字段；策略名唯一；graph=True须已创建图谱schema）"""
    await _require_kb_member(kb_id, user_id)
    if stages is not None:
        stages = _apply_stages(stages)
    fields = {
        'strategy_name': (name or '').strip() if name is not None else None,
        'embed_model': embed_model,
        'stages': stages,
        'graph': graph,
    }
    fields = {key: value for key, value in fields.items() if value is not None}
    if not fields:
        raise BusinessError('请提交需要修改的字段', code=40010, status_code=400)
    if 'strategy_name' in fields and await strategy_repository.strategy_name_exists(
            kb_id, fields['strategy_name'], except_id=strategy_id):
        raise BusinessError('该知识库下已存在同名策略',
                            code=CODE_STRATEGY_NAME_CONFLICT, status_code=409)
    # 修改后 graph=True（含未提交graph但原策略已开启）时均要求schema已创建
    final_graph = fields.get('graph')
    if final_graph is None:
        existing = await strategy_repository.get_strategy(kb_id, strategy_id)
        if not existing:
            raise BusinessError('策略不存在', code=CODE_STRATEGY_NOT_FOUND, status_code=404)
        final_graph = existing['graph']
    if final_graph:
        await _require_graph_schema(kb_id)
    strategy = await strategy_repository.update_strategy(kb_id, strategy_id, fields)
    if not strategy:
        raise BusinessError('策略不存在', code=CODE_STRATEGY_NOT_FOUND, status_code=404)
    return strategy


async def delete_parse_strategy(kb_id: int, strategy_id: int, user_id: int) -> None:
    """删除策略"""
    await _require_kb_member(kb_id, user_id)
    if not await strategy_repository.delete_strategy(kb_id, strategy_id):
        raise BusinessError('策略不存在', code=CODE_STRATEGY_NOT_FOUND, status_code=404)
