from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from infrastructure.models import RepoEmbeddingRunRecord, RepoFileSummaryRunRecord, RepoRunRecord
from infrastructure.repositories import (
    RepoEmbeddingDiagnosticRepository,
    RepoEmbeddingRepository,
    RepoEmbeddingRunRepository,
    RepoFileSummaryRunRepository,
    RepoRunRepository,
    RepoFileSummaryRepository,
)
from schemas.repo_knowledge_embedding import RepoEmbeddingRunCreateRequest
from services.repo_knowledge.embeddings.model_factory import (
    RepoEmbeddingModel,
    RepoEmbeddingModelFactoryError,
    create_repo_embedding_model,
)
from services.repo_knowledge.embeddings.text_builder import build_file_summary_embedding_text

logger = logging.getLogger(__name__)


class RepoEmbeddingError(Exception):
    """Raised when an embedding run request cannot be accepted."""


@dataclass(slots=True)
class EmbeddingCounters:
    """Mutable counters tracked while processing one embedding run."""

    subjects_seen: int = 0
    subjects_embedded: int = 0
    subjects_failed: int = 0


class RepoKnowledgeEmbeddingService:
    """Application service for embedding run APIs."""

    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.run_repo = RepoRunRepository(session)
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.embedding_run_repo = RepoEmbeddingRunRepository(session)
        self.embedding_repo = RepoEmbeddingRepository(session)

    async def create_embedding_run(
        self,
        payload: RepoEmbeddingRunCreateRequest,
    ) -> RepoEmbeddingRunRecord:
        settings = get_settings()
        source_run = await self._resolve_source_run(source_run_id=payload.source_run_id)
        file_summary_run = await self._resolve_file_summary_run(
            source_file_summary_run_id=payload.source_file_summary_run_id,
            source_run=source_run,
        )
        if file_summary_run is None:
            raise RepoEmbeddingError("No completed file_summary run found for source_run_id")

        if source_run is not None and file_summary_run.source_run_id != source_run.id:
            raise RepoEmbeddingError(
                "source_file_summary_run_id does not belong to the provided source_run_id/repo_run_id"
            )

        if source_run is None:
            source_run = await self._resolve_source_run(source_run_id=file_summary_run.source_run_id)
            if source_run is None:
                raise RepoEmbeddingError("source_run_id not found")

        run_fingerprint = _build_embedding_fingerprint(
            source_run_id=source_run.id,
            source_file_summary_run_id=file_summary_run.id,
            embed_model_name=settings.REPO_EMBED_MODEL_NAME,
            embed_vector_dim=settings.REPO_EMBED_VECTOR_DIM,
            kind="file_summary",
        )

        if not payload.force_reembed:
            existing = await self.embedding_run_repo.find_completed_by_fingerprint(
                source_run_id=source_run.id,
                source_file_summary_run_id=file_summary_run.id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                run_fingerprint=run_fingerprint,
            )
            if existing is not None:
                logger.info(
                    "Reusing completed embedding run embedding_run_id=%s source_run_id=%s file_summary_run_id=%s",
                    existing.id,
                    source_run.id,
                    file_summary_run.id,
                )
                return existing

        run = await self.embedding_run_repo.create(
            source_run_id=source_run.id,
            source_file_summary_run_id=file_summary_run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            run_fingerprint=run_fingerprint,
        )
        logger.info(
            "Created embedding run embedding_run_id=%s source_run_id=%s file_summary_run_id=%s",
            run.id,
            run.source_run_id,
            run.source_file_summary_run_id,
        )
        return run

    async def _resolve_source_run(self, *, source_run_id: str | None) -> RepoRunRecord | None:
        """Return source run when provided and completed, otherwise None."""

        if source_run_id is None:
            return None
        source_run = await self.run_repo.get_scoped(
            source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if source_run is None:
            raise RepoEmbeddingError("source_run_id not found")
        if source_run.status not in {"completed", "skipped_duplicate"}:
            raise RepoEmbeddingError("source_run_id must be completed or skipped_duplicate")
        return source_run

    async def _resolve_file_summary_run(
        self,
        *,
        source_file_summary_run_id: str | None,
        source_run: RepoRunRecord | None,
    ) -> RepoFileSummaryRunRecord | None:
        """Resolve file_summary run from explicit id or latest completed run for source run."""

        if source_file_summary_run_id:
            file_summary_run = await self.file_summary_run_repo.get_scoped(
                source_file_summary_run_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            if file_summary_run is None:
                raise RepoEmbeddingError("source_file_summary_run_id not found")
            if file_summary_run.status != "completed":
                raise RepoEmbeddingError("source_file_summary_run_id must be completed")
            return file_summary_run

        if source_run is None:
            return None
        return await self.file_summary_run_repo.latest_completed_for_source(
            source_run_id=source_run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

    async def get_embedding_run_status(self, *, embedding_run_id: str) -> RepoEmbeddingRunRecord | None:
        return await self.embedding_run_repo.get_scoped(
            embedding_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

    async def list_embedding_items(
        self,
        *,
        embedding_run_id: str,
        kind: str | None,
        language: str | None,
        subject_path_prefix: str | None,
        limit: int,
        offset: int,
    ):
        run = await self.embedding_run_repo.get_scoped(
            embedding_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if run is None:
            return None, None

        rows = await self.embedding_repo.list_for_embedding_run(
            embedding_run_id=run.id,
            source_run_id=run.source_run_id,
            kind=kind,
            language=language,
            subject_path_prefix=subject_path_prefix,
            limit=limit,
            offset=offset,
        )
        return run, rows


class RepoEmbeddingWorker:
    """Background worker that executes queued repository embedding runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.embedding_run_repo = RepoEmbeddingRunRepository(session)
        self.run_repo = RepoRunRepository(session)
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.summary_repo = RepoFileSummaryRepository(session)
        self.embedding_repo = RepoEmbeddingRepository(session)
        self.embedding_diagnostic_repo = RepoEmbeddingDiagnosticRepository(session)

    async def execute(self, *, embedding_run_id: str) -> None:
        settings = get_settings()
        logger.info("Repo embedding run start embedding_run_id=%s", embedding_run_id)

        run = await self.embedding_run_repo.get(embedding_run_id)
        if run is None:
            logger.warning("Repo embedding run abort: run not found embedding_run_id=%s", embedding_run_id)
            return
        if run.status not in {"queued", "failed"}:
            logger.info("Skipping embedding run %s with status=%s", run.id, run.status)
            return

        run_id_value = run.id
        await self.embedding_run_repo.mark_in_progress(run)
        await self.session.commit()

        source_run = await self.run_repo.get(run.source_run_id)
        if source_run is None:
            await self.embedding_run_repo.mark_failed(run, error_message="source_run_id not found")
            await self.session.commit()
            return
        if source_run.status not in {"completed", "skipped_duplicate"}:
            await self.embedding_run_repo.mark_failed(
                run,
                error_message=f"source run has unsupported status: {source_run.status}",
            )
            await self.session.commit()
            return

        file_summary_run = await self.file_summary_run_repo.get(run.source_file_summary_run_id)
        if file_summary_run is None:
            await self.embedding_run_repo.mark_failed(run, error_message="source_file_summary_run_id not found")
            await self.session.commit()
            return
        if file_summary_run.status != "completed":
            await self.embedding_run_repo.mark_failed(
                run,
                error_message=f"source file_summary run has unsupported status: {file_summary_run.status}",
            )
            await self.session.commit()
            return

        try:
            embedding_model = create_repo_embedding_model(settings=settings)
        except RepoEmbeddingModelFactoryError as exc:
            await self.embedding_run_repo.mark_failed(run, error_message=str(exc))
            await self.session.commit()
            return

        counters = EmbeddingCounters()
        try:
            rows = await self.summary_repo.list_for_file_summary_all(file_summary_run_id=run.source_file_summary_run_id)
            counters.subjects_seen = len(rows)
            await self.embedding_run_repo.set_counts(
                run,
                subjects_seen=counters.subjects_seen,
                subjects_embedded=counters.subjects_embedded,
                subjects_failed=counters.subjects_failed,
            )
            await self.session.commit()

            batch_size = max(1, settings.REPO_EMBED_BATCH_SIZE)
            for start in range(0, len(rows), batch_size):
                batch_rows = rows[start : start + batch_size]
                await self._process_batch(
                    run=run,
                    rows=batch_rows,
                    embedding_model=embedding_model,
                    counters=counters,
                )
                await self.embedding_run_repo.set_counts(
                    run,
                    subjects_seen=counters.subjects_seen,
                    subjects_embedded=counters.subjects_embedded,
                    subjects_failed=counters.subjects_failed,
                )
                await self.session.commit()

            if counters.subjects_seen > 0 and counters.subjects_embedded == 0:
                await self.embedding_run_repo.mark_failed(run, error_message="No subjects were embedded successfully")
            else:
                await self.embedding_run_repo.mark_completed(run)
            await self.session.commit()
            logger.info(
                "Repo embedding run finished embedding_run_id=%s seen=%s embedded=%s failed=%s",
                run.id,
                counters.subjects_seen,
                counters.subjects_embedded,
                counters.subjects_failed,
            )
        except Exception as exc:  # pragma: no cover - runtime issues
            await self.session.rollback()
            logger.exception("Repo embedding run failed embedding_run_id=%s", run_id_value)
            failed_run = await self.embedding_run_repo.get(run_id_value)
            if failed_run:
                await self.embedding_run_repo.mark_failed(failed_run, error_message=str(exc))
                await self.session.commit()

    async def _process_batch(
        self,
        *,
        run: RepoEmbeddingRunRecord,
        rows: list[tuple],
        embedding_model: RepoEmbeddingModel,
        counters: EmbeddingCounters,
    ) -> None:
        payloads: list[dict] = []
        texts: list[str] = []
        for summary, subject, snapshot in rows:
            text_payload = build_file_summary_embedding_text(
                summary=summary,
                subject=subject,
                snapshot=snapshot,
            )
            payloads.append(
                {
                    "subject_id": subject.id,
                    "kind": text_payload.kind,
                    "text_for_embedding": text_payload.text_for_embedding,
                    "text_hash": text_payload.text_hash,
                }
            )
            texts.append(text_payload.text_for_embedding)

        try:
            vectors = await embedding_model.embed_documents(texts)
            if len(vectors) != len(payloads):
                raise ValueError(
                    f"Embedding output length mismatch: expected {len(payloads)} got {len(vectors)}"
                )
            expected_dim = embedding_model.output_dimensionality
            for idx, vector in enumerate(vectors):
                _assert_embedding_dimension(
                    vector=vector,
                    expected_dim=expected_dim,
                    subject_id=payloads[idx]["subject_id"],
                )
            rows_to_upsert = [
                {
                    "embedding_run_id": run.id,
                    "source_run_id": run.source_run_id,
                    "source_file_summary_run_id": run.source_file_summary_run_id,
                    "subject_id": payload["subject_id"],
                    "kind": payload["kind"],
                    "text_for_embedding": payload["text_for_embedding"],
                    "text_hash": payload["text_hash"],
                    "embedding": vector,
                    "embedding_dims": len(vector),
                }
                for payload, vector in zip(payloads, vectors, strict=True)
            ]
            inserted = await self.embedding_repo.upsert_many(rows_to_upsert)
            counters.subjects_embedded += inserted
            return
        except Exception as exc:
            logger.warning(
                "Repo embedding batch failed, retrying per subject embedding_run_id=%s error=%s",
                run.id,
                exc,
            )

        for payload in payloads:
            try:
                vector = await embedding_model.embed_query(payload["text_for_embedding"])
                _assert_embedding_dimension(
                    vector=vector,
                    expected_dim=embedding_model.output_dimensionality,
                    subject_id=payload["subject_id"],
                )
                await self.embedding_repo.upsert_many(
                    [
                        {
                            "embedding_run_id": run.id,
                            "source_run_id": run.source_run_id,
                            "source_file_summary_run_id": run.source_file_summary_run_id,
                            "subject_id": payload["subject_id"],
                            "kind": payload["kind"],
                            "text_for_embedding": payload["text_for_embedding"],
                            "text_hash": payload["text_hash"],
                            "embedding": vector,
                            "embedding_dims": len(vector),
                        }
                    ]
                )
                counters.subjects_embedded += 1
            except Exception as exc:  # pragma: no cover - runtime model issues
                counters.subjects_failed += 1
                await self.embedding_diagnostic_repo.create(
                    embedding_run_id=run.id,
                    subject_id=payload["subject_id"],
                    severity="error",
                    message="embedding_generation_failed",
                    details={"error": str(exc), "kind": payload["kind"]},
                )


def _build_embedding_fingerprint(
    *,
    source_run_id: str,
    source_file_summary_run_id: str,
    embed_model_name: str,
    embed_vector_dim: int,
    kind: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(source_run_id.encode("utf-8"))
    digest.update(b"|")
    digest.update(source_file_summary_run_id.encode("utf-8"))
    digest.update(b"|")
    digest.update(embed_model_name.lower().encode("utf-8"))
    digest.update(b"|")
    digest.update(str(embed_vector_dim).encode("utf-8"))
    digest.update(b"|")
    digest.update(kind.lower().encode("utf-8"))
    return digest.hexdigest()


def _assert_embedding_dimension(*, vector: list[float], expected_dim: int, subject_id: str) -> None:
    actual_dim = len(vector)
    if actual_dim != expected_dim:
        raise ValueError(
            f"embedding dimension mismatch for subject_id={subject_id}: expected {expected_dim}, got {actual_dim}"
        )
