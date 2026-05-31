"""LLM 工厂：统一创建 LangChain LLM 实例。"""

import logging
from langchain_core.language_models import BaseChatModel
from core.config import (
    LLM_MODE,
    LLM_API_KEY,
    LLM_API_URL,
    LLM_API_MODEL,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
)

logger = logging.getLogger(__name__)


def create_llm(
    mode: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """根据配置创建 LangChain LLM 实例。

    Args:
        mode: "external" 或 "local"，默认读环境变量 LLM_MODE。
        temperature: 覆盖默认温度。
        max_tokens: 覆盖默认最大 token 数。
    """
    mode = mode or LLM_MODE
    temp = temperature if temperature is not None else LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else LLM_MAX_TOKENS

    if mode == "external":
        return _create_deepseek(temp, tokens)
    if mode == "local":
        return _create_ollama(temp, tokens)
    raise ValueError(f"不支持的 LLM 模式: {mode}")


def _create_deepseek(temperature: float, max_tokens: int) -> BaseChatModel:
    """创建 DeepSeek (OpenAI 兼容) LLM。"""
    from langchain_deepseek import ChatDeepSeek

    if not LLM_API_KEY:
        logger.warning("LLM_API_KEY 未设置，DeepSeek 可能无法使用")

    return ChatDeepSeek(
        model=LLM_API_MODEL,
        api_key=LLM_API_KEY,
        api_base=LLM_API_URL.replace("/chat/completions", ""),
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _create_ollama(temperature: float, max_tokens: int) -> BaseChatModel:
    """创建 Ollama 本地 LLM。"""
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_HOST,
        temperature=temperature,
        num_predict=max_tokens,
    )


def create_llm_with_fallback(**kwargs) -> BaseChatModel:
    """创建带降级的 LLM：主模式 → 备用模式。

    例: external 模式失败时降级到 local。
    """
    primary = create_llm(**kwargs)

    fallback_mode = "local" if (kwargs.get("mode") or LLM_MODE) == "external" else "external"
    try:
        fallback = create_llm(mode=fallback_mode, **kwargs)
        return primary.with_fallbacks([fallback])
    except Exception as e:
        logger.warning(f"备用 LLM 创建失败: {e}")
        return primary
