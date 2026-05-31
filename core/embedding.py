"""Embedding 模型管理：支持 Silicon Flow API 和本地 HuggingFace 两种模式。"""

import logging
from langchain_core.embeddings import Embeddings
from core.config import (
    EMBEDDING_MODE,
    EMBEDDING_MODEL,
    EMBEDDING_DEVICE,
    SILICONFLOW_API_KEY,
    SILICONFLOW_API_URL,
)

logger = logging.getLogger(__name__)

_embedding: Embeddings | None = None


def get_embedding() -> Embeddings:
    """获取全局 Embedding 模型（首次调用时加载）。

    模式由 EMBEDDING_MODE 控制:
    - "api":   Silicon Flow 远程 API（默认，零配置）
    - "local": HuggingFace 本地模型（需手动下载模型）
    """
    global _embedding
    if _embedding is not None:
        return _embedding

    if EMBEDDING_MODE == "api":
        _embedding = _create_api_embedding()
    elif EMBEDDING_MODE == "local":
        _embedding = _create_local_embedding()
    else:
        raise ValueError(f"不支持的 Embedding 模式: {EMBEDDING_MODE}")

    return _embedding


def _create_api_embedding() -> Embeddings:
    """创建 Silicon Flow API Embedding。"""
    from langchain_openai import OpenAIEmbeddings

    if not SILICONFLOW_API_KEY:
        raise ValueError(
            "Silicon Flow API Key 未设置。"
            "请在 .env 中设置 SILICONFLOW_API_KEY=sk-xxx"
        )

    logger.info(f"使用 Silicon Flow API Embedding: {EMBEDDING_MODEL}")
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=SILICONFLOW_API_KEY,
        openai_api_base=SILICONFLOW_API_URL,
        check_embedding_ctx_length=False,
    )


def _create_local_embedding() -> Embeddings:
    """创建本地 HuggingFace Embedding。"""
    from langchain_huggingface import HuggingFaceEmbeddings

    logger.info(f"使用本地 Embedding: {EMBEDDING_MODEL} (device={EMBEDDING_DEVICE})")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": EMBEDDING_DEVICE},
        encode_kwargs={"normalize_embeddings": True},
    )
