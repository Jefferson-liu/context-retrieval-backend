"""End-to-end smoke test for the Milvus vector-store pipeline.

This script ingests a synthetic document using the existing service layer,
executes a semantic query, and verifies that Milvus returns the expected chunk.
It relies on lightweight stub implementations for the embedder, chunker, and LLM
provider so that no external models are required.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import math
import os
import sys
import uuid
from contextlib import ExitStack
from dataclasses import dataclass
from typing import List, Sequence
from unittest.mock import patch

from config import settings
from infrastructure.context import ContextScope
from infrastructure.database.database import SessionLocal
from services.document.processing import DocumentProcessingService
from services.queries.query_service import QueryService


@dataclass
class MilvusSmokeTestResult:
    """Outcome of the Milvus smoke test."""

    document_id: int
    document_name: str
    query_id: int
    response_text: str
    sources: Sequence[str]

    def summary(self) -> str:
        formatted_sources = ", ".join(self.sources) or "<none>"
        return (
            f"Document ID {self.document_id} (\"{self.document_name}\") matched {len(self.sources)} "
            f"source(s). Query response preview: {self.response_text[:120]!r}. Sources: {formatted_sources}."
        )


class _FakeLLMProvider:
    async def get_response(self, prompt: str, max_tokens: int) -> str:  # noqa: D401 - simple stub
        del prompt, max_tokens
        return "Smoke test response generated locally."


class _FakeEmbedder:
    def __init__(self) -> None:
        self._dim = settings.MILVUS_VECTOR_DIM
        self.llm_provider = _FakeLLMProvider()

    async def generate_embedding(self, text: str) -> List[float]:
        return _vector_from_text(text, self._dim)

    async def contextualize_chunk_content(self, chunk_content: str, full_content: str) -> str:
        del full_content
        return chunk_content


class _FakeChunker:
    async def chunk_text(self, content: str) -> list[dict[str, str]]:
        return [{"content": content}]


def _vector_from_text(text: str, dim: int) -> List[float]:
    """Create a deterministic, normalized vector derived from text."""

    values = []
    for index in range(dim):
        digest = hashlib.sha256(f"{text}:{index}".encode("utf-8")).digest()
        raw = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
        values.append(raw * 2.0 - 1.0)

    norm = math.sqrt(sum(component * component for component in values))
    if norm == 0:
        return values
    return [component / norm for component in values]


async def run_smoke_test(*, cleanup: bool = True, verbose: bool = True) -> MilvusSmokeTestResult:
    """
    Execute the Milvus smoke test.

    Args:
        cleanup: When True, delete the smoke-test document after the run.
        verbose: When True, print incremental progress messages.

    Returns:
        MilvusSmokeTestResult describing the ingestion/search outcome.

    Raises:
        RuntimeError: If the application is not configured for the Milvus backend.
    """

    if settings.VECTOR_STORE_MODE != "milvus":
        raise RuntimeError(
            "VECTOR_STORE_MODE must be set to 'milvus' to run this smoke test."
        )

    tenant_id = int(os.getenv("SMOKE_TEST_TENANT_ID", "1"))
    project_id = int(os.getenv("SMOKE_TEST_PROJECT_ID", "1"))
    user_id = os.getenv("SMOKE_TEST_USER_ID", "milvus-smoke")

    context = ContextScope(
        tenant_id=tenant_id,
        project_ids=[project_id],
        user_id=user_id,
    )

    doc_content = "Milvus end-to-end smoke test document."
    query_text = doc_content
    document_name = f"milvus-smoke-{uuid.uuid4().hex}.txt"

    if verbose:
        print("[milvus-smoke] Starting session...")

    async with SessionLocal() as session:
        result: MilvusSmokeTestResult | None = None
        document_id: int | None = None

        with ExitStack() as stack:
            stack.enter_context(patch("services.document.processing.Chunker", _FakeChunker))
            stack.enter_context(patch("services.document.processing.Embedder", _FakeEmbedder))
            stack.enter_context(patch("services.queries.query_service.Embedder", _FakeEmbedder))

            doc_service = DocumentProcessingService(session, context)
            query_service = QueryService(session, context)

            if verbose:
                print("[milvus-smoke] Uploading synthetic document...")

            try:
                document_id = await doc_service.upload_and_process_document(
                    context=doc_content,
                    doc_name=document_name,
                    doc_type="text/plain",
                )
                await session.commit()

                if verbose:
                    print(f"[milvus-smoke] Document stored with ID {document_id}; querying...")

                query_result = await query_service.process_query(query_text)
                await session.commit()

                sources = [src["doc_name"] for src in query_result.get("sources", [])]
                result = MilvusSmokeTestResult(
                    document_id=document_id,
                    document_name=document_name,
                    query_id=int(query_result.get("query_id", 0)),
                    response_text=query_result.get("response", ""),
                    sources=sources,
                )

                if verbose:
                    print("[milvus-smoke] Query completed successfully.")
            except Exception:
                await session.rollback()
                raise
            finally:
                if cleanup and document_id is not None:
                    if verbose:
                        print("[milvus-smoke] Cleaning up test document...")
                    try:
                        removed = await doc_service.delete_document(document_id)
                        if not removed and verbose:
                            print(
                                f"[milvus-smoke] Warning: document {document_id} was not removed.",
                                file=sys.stderr,
                            )
                    finally:
                        await session.commit()

        assert result is not None  # For type checkers; result is set on success.
        return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Milvus end-to-end smoke test.")
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Skip cleanup so the smoke-test document remains in the database and Milvus.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages; only emit the final summary.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    try:
        result = asyncio.run(run_smoke_test(cleanup=not args.keep_data, verbose=not args.quiet))
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"Milvus smoke test failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print("[milvus-smoke] Test succeeded!")
    print(result.summary())


if __name__ == "__main__":
    main()
