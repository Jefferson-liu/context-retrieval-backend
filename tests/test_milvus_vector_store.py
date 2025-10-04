from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pytest
from unittest.mock import AsyncMock

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.vector_store.gateway import VectorRecord
from infrastructure.vector_store.milvus import milvus_store as milvus_store_module
from infrastructure.vector_store.milvus.milvus_store import MilvusVectorStore


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@dataclass
class _MappingResult:
    rows: List[Dict[str, Any]]

    def all(self) -> List[Dict[str, Any]]:
        return self.rows


@dataclass
class _ExecuteResult:
    rows: List[Dict[str, Any]]

    def mappings(self) -> _MappingResult:
        return _MappingResult(self.rows)


class _FakeSession:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self.rows = rows
        self.executed = False

    async def execute(self, _stmt) -> _ExecuteResult:
        self.executed = True
        return _ExecuteResult(self.rows)


@pytest.mark.anyio
async def test_upsert_rejects_dimension_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MilvusVectorStore(db=_FakeSession([]))
    store._vector_dim = 3
    record = VectorRecord(chunk_id=1, embedding=[0.1, 0.2], tenant_id=1, project_id=1)

    with pytest.raises(ValueError):
        await store.upsert_vectors([record])


@pytest.mark.anyio
async def test_upsert_invokes_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MilvusVectorStore(db=_FakeSession([]))
    store._vector_dim = 2

    collection = object()
    monkeypatch.setattr(store, "_get_collection", AsyncMock(return_value=collection))
    delete_mock = AsyncMock()
    insert_mock = AsyncMock()
    monkeypatch.setattr(milvus_store_module, "delete_embeddings", delete_mock)
    monkeypatch.setattr(milvus_store_module, "insert_embeddings", insert_mock)

    records = [
        VectorRecord(chunk_id=1, embedding=[0.1, 0.2], tenant_id=1, project_id=1),
        VectorRecord(chunk_id=2, embedding=[0.3, 0.4], tenant_id=1, project_id=1),
    ]

    await store.upsert_vectors(records)

    delete_mock.assert_awaited_once()
    insert_mock.assert_awaited_once()


@pytest.mark.anyio
async def test_search_returns_ordered_results(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {"id": 1, "context": "chunk-a", "content": "raw-a", "doc_id": 10, "doc_name": "Doc A"},
        {"id": 2, "context": "chunk-b", "content": "raw-b", "doc_id": 11, "doc_name": "Doc B"},
    ]
    session = _FakeSession(rows)
    store = MilvusVectorStore(db=session)
    store._vector_dim = 2

    monkeypatch.setattr(store, "_get_collection", AsyncMock(return_value=object()))

    search_mock = AsyncMock(return_value=[(2, 0.8), (1, 0.7)])
    monkeypatch.setattr(milvus_store_module, "search_embeddings", search_mock)

    results = await store.search(
        [0.1, 0.2],
        tenant_id=1,
        project_ids=[101, 102],
        top_k=5,
    )

    kwargs = search_mock.await_args.kwargs
    assert kwargs["filter_expression"] == "tenant_id == 1 && project_id in [101, 102]"
    assert [r.chunk_id for r in results] == [2, 1]
    assert results[0].doc_name == "Doc B"
    assert results[0].similarity_score == 0.8
    assert results[0].content == "raw-b"
    assert session.executed is True