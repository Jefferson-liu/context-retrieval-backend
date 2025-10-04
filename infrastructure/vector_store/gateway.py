from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from schemas.responses.vector_search_result import VectorSearchResult


@dataclass(slots=True)
class VectorRecord:
    """Container for vector embeddings scoped to a tenant/project."""

    chunk_id: int
    embedding: Sequence[float]
    tenant_id: int
    project_id: int


class VectorStoreGateway(Protocol):
    """Abstraction over vector storage/search backends."""

    async def upsert_vectors(self, records: Sequence[VectorRecord]) -> None:
        """Insert or update the provided embeddings."""

    async def delete_vectors(
        self,
        chunk_ids: Sequence[int],
        *,
        tenant_id: int,
        project_id: int | None = None,
    ) -> None:
        """Remove embeddings for the provided chunk ids."""

    async def search(
        self,
        query_embedding: Sequence[float],
        *,
        tenant_id: int,
        project_ids: Sequence[int],
        top_k: int = 10,
    ) -> Sequence[VectorSearchResult]:
        """Perform similarity search constrained to the supplied scope."""
