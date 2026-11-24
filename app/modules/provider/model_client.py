"""模型提供商连接测试：调用各家模型列表接口并归一化模型目录

不同厂商的鉴权方式与响应结构不同：
- OpenAI 兼容协议（大多数提供商）：Authorization: Bearer <API Key>，响应 data 列表
- Anthropic：x-api-key + anthropic-version 请求头，响应 data 列表
- Google Gemini：x-goog-api-key 请求头，响应 models 列表
"""

from typing import Any, Optional

import httpx

from config.settings import settings
from modules.provider.constants import PROVIDER_API_STYLE


class ProviderConnectionError(Exception):
    """测试连接失败（网络、鉴权或响应格式异常）"""


def _models_url(base_url: str) -> str:
    base = base_url.strip().rstrip('/')
    return base if base.endswith('/models') else f'{base}/models'


def _api_style(provider_name: str) -> str:
    return PROVIDER_API_STYLE.get(provider_name, 'openai')


def _infer_model_type(model_id: str) -> str:
    """按模型名推断类型，便于前端区分对话/嵌入/重排模型"""
    name = model_id.lower()
    if 'embed' in name:
        return 'embedding'
    if 'rerank' in name:
        return 'rerank'
    if any(token in name for token in ('whisper', 'tts', 'speech', 'transcribe')):
        return 'audio'
    if 'moderation' in name:
        return 'moderation'
    return 'chat'


def _extract_error_message(response: httpx.Response) -> str:
    """尽量从厂商错误响应中提取可读文案"""
    try:
        payload = response.json()
    except ValueError:
        return ''
    if not isinstance(payload, dict):
        return ''
    error = payload.get('error')
    if isinstance(error, dict):
        return str(error.get('message') or error.get('type') or '')
    if isinstance(error, str):
        return error
    return str(payload.get('message') or '')


def _provider_error(response: httpx.Response) -> ProviderConnectionError:
    status = response.status_code
    detail = _extract_error_message(response)[:200]
    if status in (401, 403):
        message = 'API Key 无效或无权访问模型列表'
    elif status == 404:
        message = '模型列表接口不存在，请检查 API Base URL'
    else:
        message = f'模型服务返回错误（HTTP {status}）'
    if detail:
        message = f'{message}：{detail}'
    return ProviderConnectionError(message)


def _parse_model_item(item: Any, style: str) -> Optional[dict]:
    """解析单条模型记录为统一结构 { id, name, type }"""
    if isinstance(item, str):
        model_id = item.strip()
        return {'id': model_id, 'name': model_id, 'type': _infer_model_type(model_id)} if model_id else None
    if not isinstance(item, dict):
        return None

    if style == 'gemini':
        raw_id = str(item.get('name') or '').strip()
        model_id = raw_id[len('models/'):] if raw_id.startswith('models/') else raw_id
        methods = [str(method).lower() for method in (item.get('supportedGenerationMethods') or [])]
        model_type = 'embedding' if any('embed' in method for method in methods) else 'chat'
    else:
        model_id = str(item.get('id') or item.get('name') or '').strip()
        declared_type = str(item.get('model_type') or item.get('type') or '').lower()
        model_type = (
            declared_type if declared_type in {'chat', 'embedding', 'rerank'} else _infer_model_type(model_id)
        )

    if not model_id:
        return None
    display_name = str(item.get('display_name') or item.get('displayName') or model_id)
    return {'id': model_id, 'name': display_name, 'type': model_type}


def _parse_models(payload: Any, style: str) -> list[dict]:
    """兼容 OpenAI data / Gemini models 等响应结构，按模型 ID 去重"""
    if isinstance(payload, list):
        items: list = payload
    elif isinstance(payload, dict):
        items = payload.get('models') if style == 'gemini' else payload.get('data')
        if not isinstance(items, list):
            alternate = payload.get('models') or payload.get('data')
            items = alternate if isinstance(alternate, list) else []
    else:
        items = []

    models: list[dict] = []
    seen: set[str] = set()
    for item in items:
        parsed = _parse_model_item(item, style)
        if not parsed or parsed['id'] in seen:
            continue
        seen.add(parsed['id'])
        models.append(parsed)
    return models


def _build_request(
    provider_name: str, base_url: str, api_key: str,
) -> tuple[str, dict[str, str]]:
    """按厂商协议构造模型列表请求地址与请求头"""
    style = _api_style(provider_name)
    url = _models_url(base_url)
    headers = {'Accept': 'application/json'}
    if style == 'gemini':
        headers['x-goog-api-key'] = api_key
    elif style == 'anthropic':
        headers['x-api-key'] = api_key
        headers['anthropic-version'] = '2023-06-01'
    elif api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    return url, headers


async def fetch_models(provider_name: str, base_url: str, api_key: str) -> list[dict]:
    """调用厂商模型列表接口，返回统一结构的模型目录"""
    style = _api_style(provider_name)
    url, headers = _build_request(provider_name, base_url, api_key)

    try:
        timeout = httpx.Timeout(settings.MODEL_READ_TIMEOUT, connect=settings.MODEL_CONNECT_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise ProviderConnectionError('连接超时，请检查 API Base URL 或网络') from exc
    except httpx.HTTPError as exc:
        raise ProviderConnectionError('无法连接到模型服务，请检查 API Base URL 或网络') from exc

    if response.status_code >= 400:
        raise _provider_error(response)

    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderConnectionError('模型服务返回内容不是合法 JSON') from exc

    return _parse_models(payload, style)
