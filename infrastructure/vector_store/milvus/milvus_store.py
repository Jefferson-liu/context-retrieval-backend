from __future__ import annotations

import asyncio
from typing import Any, Dict, Sequence

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from infrastructure.database.models.documents import Chunk, Document
from schemas.responses.vector_search_result import VectorSearchResult

from ..gateway import VectorRecord, VectorStoreGateway
from .milvus_client import MilvusClientFactory
from .milvus_queries import delete_embeddings, insert_embeddings, search_embeddings
from .milvus_schema import MilvusCollectionSpec, ensure_collection


logger = logging.getLogger(__name__)


class MilvusVectorStore(VectorStoreGateway):
    """Concrete VectorStoreGateway backed by Milvus."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._collection_name = settings.MILVUS_COLLECTION_NAME
        self._vector_dim = settings.MILVUS_VECTOR_DIM
        self._consistency_level = settings.MILVUS_CONSISTENCY_LEVEL
        self._metric_type = "IP"
        self._index_params: Dict[str, object] = {
            "index_type": "HNSW",
            "metric_type": self._metric_type,
            "params": {"M": 16, "efConstruction": 200},
        }
        self._search_params: Dict[str, object] = {
            "metric_type": self._metric_type,
            "params": {"ef": 64},
        }

        self._client_factory = MilvusClientFactory(
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
            username=settings.MILVUS_USERNAME,
            password=settings.MILVUS_PASSWORD,
        )

        self._collection = None
        self._collection_lock = asyncio.Lock()

    async def _get_collection(self):
        if self._collection is not None:
            return self._collection

        async with self._collection_lock:
            if self._collection is not None:
                return self._collection

            spec = MilvusCollectionSpec(
                name=self._collection_name,
                primary_field="chunk_id",
                vector_field="embedding",
                vector_dimension=self._vector_dim,
                metric_type=self._metric_type,
                index_params=self._index_params,
            )

            logger.info(
                "Ensuring Milvus collection '%s' (dim=%s, metric=%s)",
                spec.name,
                spec.vector_dimension,
                spec.metric_type,
            )
            self._collection = await ensure_collection(self._client_factory, spec)
            return self._collection

    async def upsert_vectors(self, records: Sequence[VectorRecord]) -> None:
        records_list = list(records)
        if not records_list:
            return

        if any(len(record.embedding) != self._vector_dim for record in records_list):
            raise ValueError(
                "Embedding dimension mismatch while writing to Milvus: "
                f"expected {self._vector_dim}."
            )

        collection = await self._get_collection()
        chunk_ids = [record.chunk_id for record in records_list]

        logger.info(
            "Milvus upsert: deleting %d existing embeddings before insert",
            len(chunk_ids),
        )

        await delete_embeddings(collection, chunk_ids)

        logger.info(
            "Milvus upsert: inserting %d embeddings (collection=%s)",
            len(records_list),
            self._collection_name,
        )

        await insert_embeddings(collection, records_list)

    async def delete_vectors(
        self,
        chunk_ids: Sequence[int],
        *,
        tenant_id: int,
        project_id: int | None = None,
    ) -> None:  # noqa: D401 - See VectorStoreGateway for description
        del tenant_id, project_id  # Deletion is chunk scoped.

        collection = await self._get_collection()

        logger.info(
            "Milvus delete: removing %d embeddings by chunk_id", len(chunk_ids)
        )

        await delete_embeddings(collection, chunk_ids)

    async def search(
        self,
        query_embedding: Sequence[float],
        *,
        tenant_id: int,
        project_ids: Sequence[int],
        top_k: int = 10,
    ) -> Sequence[VectorSearchResult]:
        if len(query_embedding) != self._vector_dim:
            raise ValueError(
                "Embedding dimension mismatch while querying Milvus: "
                f"expected {self._vector_dim}."
            )

        if not project_ids:
            return []

        collection = await self._get_collection()
        filter_expression = self._build_filter_expression(tenant_id, project_ids)

        logger.info(
            "Milvus search: top_k=%d, tenant_id=%d, projects=%s",
            top_k,
            tenant_id,
            ",".join(str(pid) for pid in project_ids),
        )

        hits = await search_embeddings(
            collection,
            query_embedding,
            limit=top_k,
            filter_expression=filter_expression,
            search_params=self._search_params,
            consistency_level=self._consistency_level,
        )

        chunk_ids = [chunk_id for chunk_id, _ in hits]
        chunk_rows = await self._fetch_chunks(chunk_ids)

        return [
            VectorSearchResult(
                chunk_id=chunk_id,
                context=row["context"],
                content=row["content"],
                doc_id=row["doc_id"],
                doc_name=row["doc_name"],
                similarity_score=score,
            )
            for chunk_id, score in hits
            if (row := chunk_rows.get(chunk_id)) is not None
        ]

    def _build_filter_expression(self, tenant_id: int, project_ids: Sequence[int]) -> str:
        project_clause = ", ".join(str(pid) for pid in project_ids)
        return f"tenant_id == {tenant_id} && project_id in [{project_clause}]"

    async def _fetch_chunks(self, chunk_ids: Sequence[int]) -> Dict[int, Any]:
        if not chunk_ids:
            return {}

        stmt = (
            select(
                Chunk.id,
                Chunk.context,
                Chunk.content,
                Chunk.doc_id,
                Document.doc_name,
            )
            .join(Document, Chunk.doc_id == Document.id)
            .where(Chunk.id.in_(chunk_ids))
        )

        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        return {row["id"]: row for row in rows}
