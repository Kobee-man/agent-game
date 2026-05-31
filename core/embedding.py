"""Embedding 模型管理：本地 HuggingFace 模型（懒加载单例）。"""

import logging
from langchain_huggingface import HuggingFaceEmbeddings
from core.config import EMBEDDING_MODEL, EMBEDDING_DEVICE

logger = logging.getLogger(__name__)

_embedding: HuggingFaceEmbeddings | None = None


def get_embedding() -> HuggingFaceEmbeddings:
    """获取全局 Embedding 模型（首次调用时加载）。"""
    global _embedding
    if _embedding is None:
        logger.info(f"加载 Embedding 模型: {EMBEDDING_MODEL} (device={EMBEDDING_DEVICE})")
        _embedding = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": EMBEDDING_DEVICE},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("Embedding 模型加载完成")
    return _embedding
