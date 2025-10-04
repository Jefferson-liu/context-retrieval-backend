from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, Sequence, Tuple

from pymilvus import Collection

from ..gateway import VectorRecord


async def insert_embeddings(collection: Collection, records: Iterable[VectorRecord]) -> None:
    """Insert embeddings into the Milvus collection."""

    records_list = list(records)
    if not records_list:
        return

    chunk_ids = [int(record.chunk_id) for record in records_list]
    tenant_ids = [int(record.tenant_id) for record in records_list]
    project_ids = [int(record.project_id) for record in records_list]
    embeddings = [list(record.embedding) for record in records_list]

    loop = asyncio.get_event_loop()

    def _insert() -> None:
        collection.insert([chunk_ids, tenant_ids, project_ids, embeddings])
        collection.flush()

    await loop.run_in_executor(None, _insert)


async def delete_embeddings(collection: Collection, chunk_ids: Sequence[int]) -> None:
    """Delete embeddings for the provided chunk IDs."""

    ids = list(chunk_ids)
    if not ids:
        return

    if len(ids) == 1:
        expr = f"chunk_id == {ids[0]}"
    else:
        values = ", ".join(str(value) for value in ids)
        expr = f"chunk_id in [{values}]"
    loop = asyncio.get_event_loop()

    def _delete() -> None:
        collection.delete(expr)
        collection.flush()

    await loop.run_in_executor(None, _delete)


async def search_embeddings(
    collection: Collection,
    query_vector: Sequence[float],
    *,
    limit: int,
    filter_expression: str | None,
    search_params: Dict[str, Any],
    consistency_level: str,
) -> Sequence[Tuple[int, float]]:
    """Run a similarity search against the Milvus collection and return (chunk_id, score)."""

    loop = asyncio.get_event_loop()

    def _search() -> Sequence[Tuple[int, float]]:
        results = collection.search(
            data=[list(query_vector)],
            anns_field="embedding",
            param=search_params,
            limit=limit,
            expr=filter_expression,
            output_fields=["chunk_id"],
            consistency_level=consistency_level,
        )

        hits = results[0] if results else []
        return [(int(hit.id), float(hit.score)) for hit in hits]

    return await loop.run_in_executor(None, _search)
