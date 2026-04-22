from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from infrastructure.repositories import (
    RepoEdgeRepository,
    RepoEmbeddingRepository,
    RepoEmbeddingRunRepository,
    RepoRunRepository,
    RepoFileSummaryRepository,
)
from services.repo_knowledge.embeddings.model_factory import (
    RepoEmbeddingModelFactoryError,
    create_repo_embedding_model,
)
from services.repo_knowledge.embeddings.text_builder import FILE_SUMMARY_KIND
from services.repo_knowledge.retrieval.business_reranker import (
    BusinessLogicRerankerError,
    create_business_logic_reranker,
)
from services.repo_knowledge.retrieval.types import ContextCandidate, ContextPackItem

logger = logging.getLogger(__name__)


class RepoContextPackError(Exception):
    """Raised when a context pack request cannot be fulfilled."""


class RepoContextPackService:
    """Builds context packs from summary embeddings + graph neighborhood expansion."""

    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.run_repo = RepoRunRepository(session)
        self.embedding_run_repo = RepoEmbeddingRunRepository(session)
        self.embedding_repo = RepoEmbeddingRepository(session)
        self.summary_repo = RepoFileSummaryRepository(session)
        self.edge_repo = RepoEdgeRepository(session)

    async def build_context_pack(
        self,
        *,
        source_run_id: str,
        query: str,
        top_k: int,
        candidate_k: int,
        neighbor_limit_each_direction: int,
    ) -> dict:
        settings = get_settings()

        source_run = await self.run_repo.get_scoped(
            source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if source_run is None:
            raise RepoContextPackError("Source run not found")

        embedding_run = await self.embedding_run_repo.latest_completed_for_source(
            source_run_id=source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if embedding_run is None:
            raise RepoContextPackError("No completed embedding run found for source run")

        try:
            embedding_model = create_repo_embedding_model(settings=settings)
        except RepoEmbeddingModelFactoryError as exc:
            raise RepoContextPackError(str(exc)) from exc

        query_embedding = await embedding_model.embed_query(query)
        candidate_hits = await self.embedding_repo.search_similar(
            embedding_run_id=embedding_run.id,
            kind=FILE_SUMMARY_KIND,
            query_embedding=query_embedding,
            limit=max(1, candidate_k),
        )

        candidates = await self._hydrate_candidates(
            source_run_id=source_run_id,
            source_file_summary_run_id=embedding_run.source_file_summary_run_id,
            candidate_hits=candidate_hits,
        )
        if not candidates:
            return {
                "source_run_id": source_run_id,
                "embedding_run_id": embedding_run.id,
                "file_summary_run_id": embedding_run.source_file_summary_run_id,
                "query": query,
                "repo_brief": "No candidate summaries matched this query.",
                "rerank_applied": False,
                "items": [],
            }

        rerank_applied = False
        rerank_reason_map: dict[str, str | None] = {}
        rerank_score_map = {item.subject_id: item.similarity_score for item in candidates}
        try:
            reranker = create_business_logic_reranker(settings=settings)
            reranked = await reranker.rerank(query=query, candidates=candidates)
            rerank_score_map = {item.subject_id: item.rerank_score for item in reranked}
            rerank_reason_map = {item.subject_id: item.reason for item in reranked}
            rerank_applied = True
        except BusinessLogicRerankerError as exc:
            logger.warning("Repo context pack rerank disabled due to setup error: %s", exc)
        except Exception as exc:  # pragma: no cover - runtime model/network issues
            logger.warning("Repo context pack rerank failed, falling back to similarity ordering: %s", exc)

        ranked_items: list[ContextPackItem] = []
        for candidate in candidates:
            similarity_score = _clamp_score(candidate.similarity_score)
            rerank_score = _clamp_score(rerank_score_map.get(candidate.subject_id, similarity_score))
            final_score = _clamp_score((0.65 * rerank_score) + (0.35 * similarity_score))
            ranked_items.append(
                ContextPackItem(
                    candidate=candidate,
                    rerank_score=rerank_score,
                    final_score=final_score,
                    rerank_reason=rerank_reason_map.get(candidate.subject_id),
                )
            )

        ranked_items.sort(key=lambda item: item.final_score, reverse=True)
        selected = ranked_items[: max(1, top_k)]

        for item in selected:
            item.neighbors = await self.edge_repo.list_neighbors_for_file(
                run_id=source_run_id,
                subject_id=item.candidate.subject_id,
                limit_each_direction=max(1, neighbor_limit_each_direction),
            )
            item.symbol_hints = await self.edge_repo.list_symbol_hints_for_file(
                run_id=source_run_id,
                file_subject_id=item.candidate.subject_id,
                limit=max(1, settings.REPO_CONTEXT_SYMBOL_HINT_LIMIT),
            )

        repo_brief = _build_repo_brief(items=selected)

        return {
            "source_run_id": source_run_id,
            "embedding_run_id": embedding_run.id,
            "file_summary_run_id": embedding_run.source_file_summary_run_id,
            "query": query,
            "repo_brief": repo_brief,
            "rerank_applied": rerank_applied,
            "items": selected,
        }

    async def _hydrate_candidates(
        self,
        *,
        source_run_id: str,
        source_file_summary_run_id: str,
        candidate_hits: list[dict],
    ) -> list[ContextCandidate]:
        if not candidate_hits:
            return []

        subject_ids = [str(item["subject_id"]) for item in candidate_hits]
        similarity_by_subject = {str(item["subject_id"]): float(item["similarity"]) for item in candidate_hits}

        rows = await self.summary_repo.list_for_subject_ids(
            file_summary_run_id=source_file_summary_run_id,
            source_run_id=source_run_id,
            subject_ids=subject_ids,
        )
        summary_by_subject: dict[str, tuple] = {row[1].id: row for row in rows}

        payload: list[ContextCandidate] = []
        for subject_id in subject_ids:
            row = summary_by_subject.get(subject_id)
            if row is None:
                continue
            summary, subject, snapshot = row
            payload.append(
                ContextCandidate(
                    subject_id=subject.id,
                    subject_path=subject.subject_path,
                    language=subject.language,
                    parse_status=snapshot.parse_status if snapshot else None,
                    overall_summary=summary.overall_summary,
                    file_cluster=list(summary.file_cluster or []),
                    important_relationships=list(summary.important_relationships or []),
                    group_function=summary.group_function,
                    similarity_score=_clamp_score(similarity_by_subject.get(subject_id, 0.0)),
                )
            )
        return payload


def _clamp_score(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _build_repo_brief(*, items: list[ContextPackItem]) -> str:
    if not items:
        return "No business-relevant summary context was available for this query."

    top = items[:3]
    group_functions = [
        item.candidate.group_function.strip()
        for item in top
        if item.candidate.group_function and item.candidate.group_function.strip()
    ]
    if group_functions:
        return "Top business functions: " + " | ".join(dict.fromkeys(group_functions))

    summaries = [item.candidate.overall_summary.strip() for item in top if item.candidate.overall_summary.strip()]
    if summaries:
        return "Top file summaries: " + " | ".join(dict.fromkeys(summaries))

    paths = [item.candidate.subject_path for item in top]
    return "Top retrieved files: " + ", ".join(paths)
