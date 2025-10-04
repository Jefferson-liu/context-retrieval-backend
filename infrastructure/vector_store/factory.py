from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import VECTOR_STORE_MODE

from .gateway import VectorStoreGateway
from .milvus import MilvusVectorStore
from .pgvector import PgVectorStore


class VectorStoreBackend(str, Enum):
    PGVECTOR = "pgvector"
    MILVUS = "milvus"


def create_vector_store(
    db: AsyncSession,
    backend: Optional[Union[VectorStoreBackend, str]] = None,
) -> VectorStoreGateway:
    """Instantiate the configured vector-store backend."""

    backend_value = backend or VECTOR_STORE_MODE
    if isinstance(backend_value, VectorStoreBackend):
        backend_key = backend_value.value
    else:
        backend_key = str(backend_value).lower().strip()

    if backend_key == VectorStoreBackend.PGVECTOR.value:
        return PgVectorStore(db)

    if backend_key == VectorStoreBackend.MILVUS.value:
        return MilvusVectorStore(db)

    raise ValueError(f"Unsupported vector store backend: {backend_value}")
