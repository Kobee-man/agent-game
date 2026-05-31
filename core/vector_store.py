"""PGVector 向量库管理。"""

import logging
from langchain_postgres import PGVector
from core.config import DATABASE_URL, VECTOR_COLLECTION_PREFIX
from core.embedding import get_embedding

logger = logging.getLogger(__name__)

# psycopg2 URL → psycopg3 URL（langchain-postgres 需要 psycopg3）
_CONNECTION_URL = DATABASE_URL.replace("+psycopg2", "+psycopg")

_stores: dict[str, PGVector] = {}


def get_vector_store(collection_name: str) -> PGVector:
    """获取指定集合的 PGVector 存储（懒缓存）。

    Args:
        collection_name: 集合名（自动加前缀），如 "puzzles", "chat_history"
    """
    full_name = f"{VECTOR_COLLECTION_PREFIX}{collection_name}"

    if full_name not in _stores:
        logger.info(f"创建向量集合: {full_name}")
        _stores[full_name] = PGVector(
            embeddings=get_embedding(),
            collection_name=full_name,
            connection=_CONNECTION_URL,
            use_jsonb=True,
            create_extension=True,
        )
    return _stores[full_name]
