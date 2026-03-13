from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from infrastructure.models import RepoFullSummaryRecord, RepoFullSummaryRunRecord
from infrastructure.repositories import (
    RepoEdgeRepository,
    RepoFileSummaryRepository,
    RepoFileSummaryRunRepository,
    RepoFullSummaryDiagnosticRepository,
    RepoFullSummaryRepository,
    RepoFullSummaryRunRepository,
    RepoRunRepository,
    RepoSubjectRepository,
)
from schemas.repo_knowledge_repo_full_summary import RepoFullSummaryRunCreateRequest
from services.repo_knowledge.repo_full_summarization import RepoFullSummarizer
from services.repo_knowledge.repo_full_summarization.types import RepoFullSummaryInput
from services.repo_knowledge.summarization.model_factory import (
    SummaryModelFactoryError,
    create_summary_chat_model,
)
from services.repo_knowledge.summarization.react_agent_runtime import AgentProtocolError

logger = logging.getLogger(__name__)

GEMINI_PROVIDER = "gemini"
GEMINI_MODEL = "gemini-3-flash-preview"


class RepoFullSummaryError(Exception):
    """Raised when a repo full-summary run request cannot be accepted."""


@dataclass(slots=True)
class RepoFullSummaryCounters:
    """Mutable counters tracked while processing one repo full-summary run."""

    files_seen: int = 0
    files_used: int = 0


class RepoKnowledgeRepoFullSummaryService:
    """Application service for repo full-summary run APIs."""

    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.run_repo = RepoRunRepository(session)
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.repo_full_summary_run_repo = RepoFullSummaryRunRepository(session)
        self.repo_full_summary_repo = RepoFullSummaryRepository(session)

    async def create_repo_full_summary_run(
        self,
        payload: RepoFullSummaryRunCreateRequest,
    ) -> RepoFullSummaryRunRecord:
        settings = get_settings()

        file_summary_run = await self.file_summary_run_repo.get_scoped(
            payload.source_file_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if file_summary_run is None:
            raise RepoFullSummaryError("source_file_summary_run_id not found")
        if file_summary_run.status != "completed":
            raise RepoFullSummaryError("source_file_summary_run_id must be completed")

        source_run = await self.run_repo.get_scoped(
            file_summary_run.source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if source_run is None:
            raise RepoFullSummaryError("source_run_id not found")
        if source_run.status not in {"completed", "skipped_duplicate"}:
            raise RepoFullSummaryError("source_run_id must be completed or skipped_duplicate")

        prompt_version = settings.REPO_FULL_SUMMARY_PROMPT_VERSION
        run_fingerprint = _build_repo_full_summary_fingerprint(
            source_run_id=source_run.id,
            source_file_summary_run_id=file_summary_run.id,
            model_provider=GEMINI_PROVIDER,
            model_name=GEMINI_MODEL,
            prompt_version=prompt_version,
        )

        if not payload.force_rerepo_summary:
            existing = await self.repo_full_summary_run_repo.find_completed_by_fingerprint(
                source_run_id=source_run.id,
                source_file_summary_run_id=file_summary_run.id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                run_fingerprint=run_fingerprint,
            )
            if existing is not None:
                logger.info(
                    "Reusing completed repo-full-summary run repo_full_summary_run_id=%s source_run_id=%s file_summary_run_id=%s",
                    existing.id,
                    source_run.id,
                    file_summary_run.id,
                )
                return existing

        run = await self.repo_full_summary_run_repo.create(
            source_run_id=source_run.id,
            source_file_summary_run_id=file_summary_run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            model_provider=GEMINI_PROVIDER,
            model_name=GEMINI_MODEL,
            prompt_version=prompt_version,
            run_fingerprint=run_fingerprint,
        )
        logger.info(
            "Created repo-full-summary run repo_full_summary_run_id=%s source_run_id=%s file_summary_run_id=%s",
            run.id,
            run.source_run_id,
            run.source_file_summary_run_id,
        )
        return run

    async def get_repo_full_summary_run_status(
        self,
        *,
        repo_full_summary_run_id: str,
    ) -> RepoFullSummaryRunRecord | None:
        return await self.repo_full_summary_run_repo.get_scoped(
            repo_full_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

    async def get_repo_full_summary_readme(
        self,
        *,
        repo_full_summary_run_id: str,
    ) -> tuple[RepoFullSummaryRunRecord, RepoFullSummaryRecord | None] | tuple[None, None]:
        run = await self.repo_full_summary_run_repo.get_scoped(
            repo_full_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if run is None:
            return None, None
        readme = await self.repo_full_summary_repo.get_for_run(repo_full_summary_run_id=run.id)
        return run, readme

    async def latest_repo_full_summary_for_source_run(
        self,
        *,
        source_run_id: str,
    ) -> tuple[RepoFullSummaryRunRecord, RepoFullSummaryRecord | None] | tuple[None, None]:
        source_run = await self.run_repo.get_scoped(
            source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if source_run is None:
            return None, None
        latest = await self.repo_full_summary_run_repo.latest_completed_for_source(
            source_run_id=source_run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if latest is None:
            return source_run, None
        readme = await self.repo_full_summary_repo.get_for_run(repo_full_summary_run_id=latest.id)
        return latest, readme


class RepoFullSummaryWorker:
    """Background worker that executes queued repo full-summary runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo_full_summary_run_repo = RepoFullSummaryRunRepository(session)
        self.repo_full_summary_repo = RepoFullSummaryRepository(session)
        self.repo_full_summary_diagnostic_repo = RepoFullSummaryDiagnosticRepository(session)
        self.run_repo = RepoRunRepository(session)
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.file_summary_repo = RepoFileSummaryRepository(session)
        self.subject_repo = RepoSubjectRepository(session)
        self.edge_repo = RepoEdgeRepository(session)

    async def execute(self, *, repo_full_summary_run_id: str) -> None:
        settings = get_settings()
        logger.info("Repo full-summary run start repo_full_summary_run_id=%s", repo_full_summary_run_id)

        run = await self.repo_full_summary_run_repo.get(repo_full_summary_run_id)
        if run is None:
            logger.warning(
                "Repo full-summary run abort: run not found repo_full_summary_run_id=%s",
                repo_full_summary_run_id,
            )
            return
        if run.status not in {"queued", "failed"}:
            logger.info("Skipping repo-full-summary run %s with status=%s", run.id, run.status)
            return

        run_id_value = run.id
        await self.repo_full_summary_run_repo.mark_in_progress(run)
        await self.session.commit()

        source_run = await self.run_repo.get(run.source_run_id)
        if source_run is None:
            await self.repo_full_summary_run_repo.mark_failed(run, error_message="source_run_id not found")
            await self.session.commit()
            return
        if source_run.status not in {"completed", "skipped_duplicate"}:
            await self.repo_full_summary_run_repo.mark_failed(
                run,
                error_message=f"source run has unsupported status: {source_run.status}",
            )
            await self.session.commit()
            return

        file_summary_run = await self.file_summary_run_repo.get(run.source_file_summary_run_id)
        if file_summary_run is None:
            await self.repo_full_summary_run_repo.mark_failed(run, error_message="source_file_summary_run_id not found")
            await self.session.commit()
            return
        if file_summary_run.status != "completed":
            await self.repo_full_summary_run_repo.mark_failed(
                run,
                error_message=f"source file_summary run has unsupported status: {file_summary_run.status}",
            )
            await self.session.commit()
            return

        try:
            chat_model = create_summary_chat_model(
                settings=settings,
                provider_override=GEMINI_PROVIDER,
                model_override=GEMINI_MODEL,
            )
        except SummaryModelFactoryError as exc:
            await self.repo_full_summary_run_repo.mark_failed(run, error_message=str(exc))
            await self.session.commit()
            return

        summarizer = RepoFullSummarizer(
            chat_model=chat_model,
            prompt_version=run.prompt_version,
            max_input_chars=settings.REPO_FULL_SUMMARY_MAX_INPUT_CHARS,
            retry_count=settings.REPO_FULL_SUMMARY_RETRY_COUNT,
            timeout_seconds=settings.REPO_FULL_SUMMARY_TIMEOUT_SECONDS,
            subject_repo=self.subject_repo,
            edge_repo=self.edge_repo,
            file_summary_repo=self.file_summary_repo,
            max_iterations=settings.REPO_FULL_SUMMARY_MAX_ITERATIONS,
        )

        counters = RepoFullSummaryCounters()
        try:
            summary_rows = await self.file_summary_repo.list_for_file_summary_all(
                file_summary_run_id=run.source_file_summary_run_id
            )
            counters.files_seen = len(summary_rows)
            await self.repo_full_summary_run_repo.set_counts(
                run,
                files_seen=counters.files_seen,
                files_used=counters.files_used,
            )
            await self.session.commit()

            result = await summarizer.summarize(
                payload=RepoFullSummaryInput(
                    source_run_id=run.source_run_id,
                    source_file_summary_run_id=run.source_file_summary_run_id,
                    repo_path=source_run.source_locator,
                    repo_address=source_run.repo_address,
                    tech_stack=_derive_tech_stack(summary_rows),
                    entry_points_trace="",
                    related_repo_info="",
                )
            )

            counters.files_used = _count_tool_summary_hits(result.raw_output.get("tool_trace", []))
            await self.repo_full_summary_repo.upsert(
                repo_full_summary_run_id=run.id,
                source_run_id=run.source_run_id,
                source_file_summary_run_id=run.source_file_summary_run_id,
                readme_markdown=result.output.readme_markdown,
                raw_output=result.raw_output,
                input_hash=result.input_hash,
            )
            await self.repo_full_summary_run_repo.set_counts(
                run,
                files_seen=counters.files_seen,
                files_used=counters.files_used,
            )
            await self.repo_full_summary_run_repo.mark_completed(run)
            await self.session.commit()
        except Exception as exc:  # pragma: no cover - runtime LLM failures
            await self.session.rollback()
            logger.exception("Repo full-summary run failed repo_full_summary_run_id=%s", run_id_value)
            failed = await self.repo_full_summary_run_repo.get(run_id_value)
            if failed is not None:
                diagnostic_code, diagnostic_message = _classify_repo_full_summary_failure(exc)
                await self.repo_full_summary_diagnostic_repo.create(
                    repo_full_summary_run_id=failed.id,
                    severity="error",
                    message=diagnostic_message,
                    details={
                        "error": str(exc),
                        "error_type": exc.__class__.__name__,
                        "diagnostic_code": diagnostic_code,
                    },
                )
                await self.repo_full_summary_run_repo.mark_failed(failed, error_message=str(exc))
                await self.session.commit()


def _build_repo_full_summary_fingerprint(
    *,
    source_run_id: str,
    source_file_summary_run_id: str,
    model_provider: str,
    model_name: str,
    prompt_version: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(source_run_id.encode("utf-8"))
    digest.update(b"|")
    digest.update(source_file_summary_run_id.encode("utf-8"))
    digest.update(b"|")
    digest.update(model_provider.lower().encode("utf-8"))
    digest.update(b"|")
    digest.update(model_name.lower().encode("utf-8"))
    digest.update(b"|")
    digest.update(prompt_version.lower().encode("utf-8"))
    return digest.hexdigest()


def _derive_tech_stack(summary_rows: list[tuple]) -> str:
    languages = sorted(
        {
            (getattr(subject, "language", "") or "").strip().lower()
            for _summary, subject, _snapshot in summary_rows
            if (getattr(subject, "language", "") or "").strip()
        }
    )
    if not languages:
        return "unknown"
    return ", ".join(languages)


def _count_tool_summary_hits(tool_trace: list[dict]) -> int:
    subject_paths: set[str] = set()
    for item in tool_trace:
        if item.get("name") != "return_file_summary":
            continue
        resolved = item.get("resolved_subject_path")
        if isinstance(resolved, str) and resolved.strip():
            subject_paths.add(resolved.strip())
    return len(subject_paths)


def _classify_repo_full_summary_failure(exc: Exception) -> tuple[str, str]:
    """Return stable diagnostic code/message pair for repo-full-summary failures."""

    raw = str(exc).lower()
    if isinstance(exc, AgentProtocolError) or "thought_signature" in raw:
        return "thought_signature_missing", "repo_full_summary_agent_protocol_failed"
    if isinstance(exc, asyncio.TimeoutError):
        return "agent_timeout", "repo_full_summary_agent_timeout"
    return "repo_full_summary_failed", "repo_full_summary_failed"
