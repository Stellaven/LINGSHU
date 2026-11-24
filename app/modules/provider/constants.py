"""供应商域常量：预置模型提供商目录（与前端模型配置页展示一致）"""

from typing import Optional

CODE_PROVIDER_NOT_FOUND = 40407  # 模型提供商不存在（HTTP 404）
CODE_INSTANCE_NOT_FOUND = 40408  # 模型实例不存在（HTTP 404）
CODE_PROVIDER_CONFIG_INCOMPLETE = 40009  # 连接配置不完整（HTTP 400）
CODE_PROVIDER_CONNECTION_FAILED = 50201  # 测试连接失败（HTTP 502）

# 模型列表接口鉴权方式：未列出的提供商默认按 OpenAI 兼容协议（Authorization: Bearer）
PROVIDER_API_STYLE: dict[str, str] = {
    'Anthropic': 'anthropic',
    'Google Gemini': 'gemini',
}


def find_provider_catalog(name: str) -> Optional[tuple[str, str, str, str, int, str]]:
    """按名称查找预置提供商目录项（忽略大小写），找不到返回 None"""
    normalized = (name or '').strip().lower()
    for entry in PROVIDER_CATALOG:
        if entry[0].lower() == normalized:
            return entry
    return None


# (name, region, color, default_base_url, sort_order, logo)
# region: global 国际 / china 国内
# logo: 厂商LOGO（随前端静态资源存放于 web/public/provider-logos）；color 仅作无LOGO时的回退底色
PROVIDER_CATALOG: list[tuple[str, str, str, str, int, str]] = [
    ('OpenAI', 'global', '#10A37F', 'https://api.openai.com/v1', 1,
     '/provider-logos/openai.svg'),
    ('Anthropic', 'global', '#D97757', 'https://api.anthropic.com/v1', 2,
     '/provider-logos/anthropic.svg'),
    ('Google Gemini', 'global', '#4285F4', 'https://generativelanguage.googleapis.com/v1beta', 3,
     '/provider-logos/gemini.svg'),
    ('DeepSeek', 'china', '#4D6BFE', 'https://api.deepseek.com/v1', 4,
     '/provider-logos/deepseek.svg'),
    ('Qwen', 'china', '#615CED', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 5,
     '/provider-logos/qwen.svg'),
    ('Zhipu AI', 'china', '#3859FF', 'https://open.bigmodel.cn/api/paas/v4', 6,
     '/provider-logos/zhipu.svg'),
    ('Kimi', 'china', '#14B8A6', 'https://api.moonshot.cn/v1', 7,
     '/provider-logos/kimi.svg'),
    ('Doubao', 'china', '#2E5CE6', 'https://ark.cn-beijing.volces.com/api/v3', 8,
     '/provider-logos/doubao.svg'),
    ('MiniMax', 'china', '#E2167E', 'https://api.minimaxi.com/v1', 9,
     '/provider-logos/minimax.svg'),
    ('腾讯混元', 'china', '#0055E9', 'https://api.hunyuan.cloud.tencent.com/v1', 10,
     '/provider-logos/hunyuan.svg'),
    ('百度', 'china', '#2932E1', 'https://qianfan.baidubce.com/v2', 11,
     '/provider-logos/baidu.svg'),
    ('科大讯飞', 'china', '#2A80E2', 'https://spark-api-open.xf-yun.com/v1', 12,
     '/provider-logos/iflytek.svg'),
    ('阶跃星辰', 'china', '#0160FF', 'https://api.stepfun.com/v1', 13,
     '/provider-logos/stepfun.svg'),
    ('Meta', 'global', '#0866FF', 'https://api.llama.com/compat/v1', 14,
     '/provider-logos/meta.svg'),
    ('xAI', 'global', '#111111', 'https://api.x.ai/v1', 15,
     '/provider-logos/xai.svg'),
    ('Ollama', 'global', '#1F2937', 'http://localhost:11434/v1', 16,
     '/provider-logos/ollama.svg'),
]
