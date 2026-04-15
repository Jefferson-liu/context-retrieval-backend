from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from infrastructure.models import RepoFileSummaryRunRecord
from infrastructure.repositories import (
    RepoChunkRepository,
    RepoEdgeRepository,
    RepoFileSummaryRunRepository,
    RepoRunRepository,
    RepoSnapshotRepository,
    RepoSubjectRepository,
    RepoFileSummaryDiagnosticRepository,
    RepoFileSummaryRepository,
    RepoFileSummaryUsageRepository,
)
from schemas.repo_knowledge_file_summary import RepoFileSummaryRunCreateRequest
from services.repo_knowledge.summarization.context_assembler import SummaryContextAssembler
from services.repo_knowledge.summarization.file_summarizer import RepoFileSummarizer
from services.repo_knowledge.summarization.model_factory import (
    SummaryModelFactoryError,
    create_summary_chat_model,
)
from services.repo_knowledge.summarization.react_agent_runtime import AgentProtocolError

logger = logging.getLogger(__name__)

GEMINI_PROVIDER = "gemini"
GEMINI_MODEL = "gemini-3-flash-preview"


class RepoFileSummaryError(Exception):
    """Raised when an file_summary run request cannot be accepted."""


@dataclass(slots=True)
class FileSummaryCounters:
    """Mutable counters tracked while processing one file_summary run."""

    files_seen: int = 0
    files_summarized: int = 0
    files_failed: int = 0


class RepoKnowledgeFileSummaryService:
    """Application service for file_summary run APIs."""

    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.run_repo = RepoRunRepository(session)
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.summary_repo = RepoFileSummaryRepository(session)
        self.summary_diagnostic_repo = RepoFileSummaryDiagnosticRepository(session)
        self.usage_repo = RepoFileSummaryUsageRepository(session)

    async def create_file_summary_run(
        self,
        payload: RepoFileSummaryRunCreateRequest,
    ) -> RepoFileSummaryRunRecord:
        settings = get_settings()
        source_run_id = _resolve_source_run_id(payload)
        source_run = await self.run_repo.get_scoped(
            source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if source_run is None:
            raise RepoFileSummaryError("source_run_id not found")
        if source_run.status not in {"completed", "skipped_duplicate"}:
            raise RepoFileSummaryError("source_run_id must be completed or skipped_duplicate")

        provider = GEMINI_PROVIDER
        model_name = GEMINI_MODEL

        prompt_version = settings.REPO_SUMMARY_PROMPT_VERSION
        run_fingerprint = _build_file_summary_fingerprint(
            source_run_id=source_run.id,
            model_provider=provider,
            model_name=model_name,
            prompt_version=prompt_version,
        )

        if not payload.force_refile_summary:
            existing = await self.file_summary_run_repo.find_completed_by_fingerprint(
                source_run_id=source_run.id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                run_fingerprint=run_fingerprint,
            )
            if existing:
                logger.info(
                    "Reusing completed file_summary run file_summary_run_id=%s source_run_id=%s",
                    existing.id,
                    source_run.id,
                )
                return existing

        run = await self.file_summary_run_repo.create(
            source_run_id=source_run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            model_provider=provider,
            model_name=model_name,
            prompt_version=prompt_version,
            run_fingerprint=run_fingerprint,
        )
        logger.info(
            "Created file_summary run file_summary_run_id=%s source_run_id=%s provider=%s model=%s (internal hard-set)",
            run.id,
            run.source_run_id,
            run.model_provider,
            run.model_name,
        )
        return run

    async def get_file_summary_run_status(self, *, file_summary_run_id: str) -> RepoFileSummaryRunRecord | None:
        return await self.file_summary_run_repo.get_scoped(
            file_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

    async def list_summaries(
        self,
        *,
        file_summary_run_id: str,
        limit: int,
        offset: int,
        language: str | None,
        parse_status: str | None,
        subject_path_prefix: str | None,
    ):
        run = await self.file_summary_run_repo.get_scoped(
            file_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if run is None:
            return None, None
        rows = await self.summary_repo.list_for_file_summary(
            file_summary_run_id=run.id,
            source_run_id=run.source_run_id,
            limit=limit,
            offset=offset,
            language=language,
            parse_status=parse_status,
            subject_path_prefix=subject_path_prefix,
        )
        return run, rows

    async def latest_summaries_for_source_run(
        self,
        *,
        source_run_id: str,
        limit: int,
        offset: int,
    ):
        source_run = await self.run_repo.get_scoped(
            source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if source_run is None:
            return None, None
        latest = await self.file_summary_run_repo.latest_completed_for_source(
            source_run_id=source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if latest is None:
            return source_run, None
        rows = await self.summary_repo.list_for_file_summary(
            file_summary_run_id=latest.id,
            source_run_id=latest.source_run_id,
            limit=limit,
            offset=offset,
            language=None,
            parse_status=None,
            subject_path_prefix=None,
        )
        return latest, rows

    async def list_diagnostics(
        self,
        *,
        file_summary_run_id: str,
        limit: int,
        offset: int,
        severity: str | None,
        subject_path_prefix: str | None,
    ):
        run = await self.file_summary_run_repo.get_scoped(
            file_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if run is None:
            return None, None
        rows = await self.summary_diagnostic_repo.list_for_file_summary(
            file_summary_run_id=run.id,
            limit=limit,
            offset=offset,
            severity=severity,
            subject_path_prefix=subject_path_prefix,
        )
        return run, rows

    async def list_usage(
        self,
        *,
        file_summary_run_id: str,
        limit: int,
        offset: int,
        status: str | None,
        subject_path_prefix: str | None,
    ):
        run = await self.file_summary_run_repo.get_scoped(
            file_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if run is None:
            return None, None
        rows = await self.usage_repo.list_for_run(
            file_summary_run_id=run.id,
            limit=limit,
            offset=offset,
            status=status,
            subject_path_prefix=subject_path_prefix,
        )
        return run, rows

    async def aggregate_usage(
        self,
        *,
        file_summary_run_id: str,
    ):
        run = await self.file_summary_run_repo.get_scoped(
            file_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if run is None:
            return None, None
        agg = await self.usage_repo.aggregate_for_run(
            file_summary_run_id=run.id,
        )
        return run, agg


@dataclass(slots=True)
class FileSummaryAgentConfig:
    """Tunable agent parameters for file-summary runs.

    Override at construction time or leave as defaults.
    Env-var overrides from settings are applied in ``from_settings()``.
    """

    max_input_chars: int = 24_000
    map_chunk_chars: int = 6_000
    retry_count: int = 2
    timeout_seconds: int = 60
    max_iterations: int = 6
    max_concurrent_files: int = 8

    @classmethod
    def from_settings(cls) -> "FileSummaryAgentConfig":
        """Build config from env-var backed settings, using class defaults as fallbacks."""
        settings = get_settings()
        return cls(
            max_input_chars=settings.REPO_SUMMARY_MAX_INPUT_CHARS,
            map_chunk_chars=settings.REPO_SUMMARY_MAP_CHUNK_CHARS,
            retry_count=settings.REPO_SUMMARY_RETRY_COUNT,
            timeout_seconds=settings.REPO_SUMMARY_TIMEOUT_SECONDS,
            max_iterations=settings.REPO_SUMMARY_MAX_ITERATIONS,
            max_concurrent_files=settings.REPO_SUMMARY_MAX_CONCURRENT_FILES,
        )


class RepoFileSummaryWorker:
    """Background worker that executes queued repository summary file_summary runs."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        agent_config: FileSummaryAgentConfig | None = None,
    ) -> None:
        self.session = session
        self.agent_config = agent_config or FileSummaryAgentConfig.from_settings()
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.run_repo = RepoRunRepository(session)
        self.snapshot_repo = RepoSnapshotRepository(session)
        self.chunk_repo = RepoChunkRepository(session)
        self.edge_repo = RepoEdgeRepository(session)
        self.subject_repo = RepoSubjectRepository(session)
        self.summary_repo = RepoFileSummaryRepository(session)
        self.summary_diagnostic_repo = RepoFileSummaryDiagnosticRepository(session)
        self.usage_repo = RepoFileSummaryUsageRepository(session)

    async def execute(self, *, file_summary_run_id: str) -> None:
        settings = get_settings()
        cfg = self.agent_config
        logger.info("Repo summary file_summary start file_summary_run_id=%s", file_summary_run_id)
        run = await self.file_summary_run_repo.get(file_summary_run_id)
        if run is None:
            logger.warning("Repo summary file_summary abort: run not found file_summary_run_id=%s", file_summary_run_id)
            return
        if run.status not in {"queued", "failed"}:
            logger.info("Skipping file_summary run %s with status=%s", run.id, run.status)
            return

        run_id_value = run.id
        await self.file_summary_run_repo.mark_in_progress(run)
        await self.session.commit()

        source_run = await self.run_repo.get(run.source_run_id)
        if source_run is None:
            await self.file_summary_run_repo.mark_failed(run, error_message="source_run_id not found")
            await self.session.commit()
            return
        if source_run.status not in {"completed", "skipped_duplicate"}:
            await self.file_summary_run_repo.mark_failed(
                run,
                error_message=f"source run has unsupported status: {source_run.status}",
            )
            await self.session.commit()
            return

        try:
            chat_model = create_summary_chat_model(
                settings=settings,
                provider_override=run.model_provider,
                model_override=run.model_name,
            )
        except SummaryModelFactoryError as exc:
            await self.file_summary_run_repo.mark_failed(run, error_message=str(exc))
            await self.session.commit()
            return

        summarizer = RepoFileSummarizer(
            chat_model=chat_model,
            prompt_version=run.prompt_version,
            max_input_chars=cfg.max_input_chars,
            map_chunk_chars=cfg.map_chunk_chars,
            retry_count=cfg.retry_count,
            timeout_seconds=cfg.timeout_seconds,
            max_iterations=cfg.max_iterations,
            subject_repo=self.subject_repo,
            edge_repo=self.edge_repo,
        )
        assembler = SummaryContextAssembler(
            chunk_repo=self.chunk_repo,
        )

        counters = FileSummaryCounters()
        try:
            files = await self.snapshot_repo.list_ingested_for_run(run_id=run.source_run_id)
            counters.files_seen = len(files)
            await self.file_summary_run_repo.set_counts(
                run,
                files_seen=counters.files_seen,
                files_summarized=counters.files_summarized,
                files_failed=counters.files_failed,
            )
            await self.session.commit()

            semaphore = asyncio.Semaphore(cfg.max_concurrent_files)
            lock = asyncio.Lock()

            async def _process_file(snapshot, subject) -> None:
                async with semaphore:
                    # --- read stage: build context from DB (serialized via lock) ---
                    async with lock:
                        try:
                            context = await assembler.build(
                                source_run_id=run.source_run_id,
                                snapshot=snapshot,
                                subject=subject,
                                repo_path=source_run.source_locator,
                                repo_address=source_run.repo_address,
                                tech_stack=subject.language or "unknown",
                            )
                        except Exception as exc:  # pragma: no cover - runtime failures
                            counters.files_failed += 1
                            diagnostic_code, diagnostic_message = _classify_file_summary_failure(exc)
                            await self.summary_diagnostic_repo.create(
                                file_summary_run_id=run.id,
                                subject_id=subject.id,
                                severity="error",
                                message=diagnostic_message,
                                details={
                                    "error": str(exc),
                                    "subject_path": subject.subject_path,
                                    "error_type": exc.__class__.__name__,
                                    "diagnostic_code": diagnostic_code,
                                },
                            )
                            await self.usage_repo.create(
                                file_summary_run_id=run.id,
                                subject_id=subject.id,
                                model_provider=run.model_provider,
                                model_name=run.model_name,
                                status="failed",
                                error_message=str(exc)[:2000],
                            )
                            await self.file_summary_run_repo.set_counts(
                                run,
                                files_seen=counters.files_seen,
                                files_summarized=counters.files_summarized,
                                files_failed=counters.files_failed,
                            )
                            await self.session.commit()
                            return

                    # --- LLM stage: summarize (runs concurrently, no lock) ---
                    try:
                        result = await summarizer.summarize(payload=context)
                    except Exception as exc:  # pragma: no cover - runtime LLM failures
                        async with lock:
                            counters.files_failed += 1
                            diagnostic_code, diagnostic_message = _classify_file_summary_failure(exc)
                            await self.summary_diagnostic_repo.create(
                                file_summary_run_id=run.id,
                                subject_id=subject.id,
                                severity="error",
                                message=diagnostic_message,
                                details={
                                    "error": str(exc),
                                    "subject_path": subject.subject_path,
                                    "error_type": exc.__class__.__name__,
                                    "diagnostic_code": diagnostic_code,
                                },
                            )
                            await self.usage_repo.create(
                                file_summary_run_id=run.id,
                                subject_id=subject.id,
                                model_provider=run.model_provider,
                                model_name=run.model_name,
                                status="failed",
                                error_message=str(exc)[:2000],
                            )
                            await self.file_summary_run_repo.set_counts(
                                run,
                                files_seen=counters.files_seen,
                                files_summarized=counters.files_summarized,
                                files_failed=counters.files_failed,
                            )
                            await self.session.commit()
                        return

                    # --- write stage: persist results (serialized via lock) ---
                    async with lock:
                        await self.summary_repo.upsert(
                            file_summary_run_id=run.id,
                            source_run_id=run.source_run_id,
                            subject_id=subject.id,
                            overall_summary=result.output.overall_summary,
                            file_cluster=result.output.file_cluster,
                            important_relationships=result.output.important_relationships,
                            group_function=result.output.group_function,
                            raw_output=result.raw_output,
                            input_hash=result.input_hash,
                        )
                        if result.usage_trace is not None:
                            trace = result.usage_trace
                            await self.usage_repo.create(
                                file_summary_run_id=run.id,
                                subject_id=subject.id,
                                model_provider=run.model_provider,
                                model_name=run.model_name,
                                status="completed",
                                total_input_tokens=trace.get("total_input_tokens", 0),
                                total_output_tokens=trace.get("total_output_tokens", 0),
                                total_tokens=trace.get("total_tokens", 0),
                                cached_input_tokens=trace.get("cached_input_tokens", 0),
                                reasoning_tokens=trace.get("reasoning_tokens", 0),
                                llm_step_count=trace.get("llm_step_count", 0),
                                tool_call_count=trace.get("tool_call_count", 0),
                                duration_ms=trace.get("duration_ms"),
                                steps=trace.get("steps", []),
                            )
                        else:
                            await self.usage_repo.create(
                                file_summary_run_id=run.id,
                                subject_id=subject.id,
                                model_provider=run.model_provider,
                                model_name=run.model_name,
                                status="skipped",
                            )
                        counters.files_summarized += 1
                        await self.file_summary_run_repo.set_counts(
                            run,
                            files_seen=counters.files_seen,
                            files_summarized=counters.files_summarized,
                            files_failed=counters.files_failed,
                        )
                        await self.session.commit()

            await asyncio.gather(*[_process_file(snapshot, subject) for snapshot, subject in files])

            if counters.files_seen > 0 and counters.files_summarized == 0:
                await self.file_summary_run_repo.mark_failed(
                    run,
                    error_message="No files were summarized successfully",
                )
            else:
                await self.file_summary_run_repo.mark_completed(run)
            await self.session.commit()
        except Exception as exc:  # pragma: no cover - run-level failures
            await self.session.rollback()
            logger.exception("Repo summary file_summary failed file_summary_run_id=%s", run_id_value)
            failed = await self.file_summary_run_repo.get(run_id_value)
            if failed:
                await self.file_summary_run_repo.mark_failed(failed, error_message=str(exc))
                await self.session.commit()


def _build_file_summary_fingerprint(
    *,
    source_run_id: str,
    model_provider: str,
    model_name: str,
    prompt_version: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(source_run_id.encode("utf-8"))
    digest.update(b"|")
    digest.update(model_provider.lower().encode("utf-8"))
    digest.update(b"|")
    digest.update(model_name.lower().encode("utf-8"))
    digest.update(b"|")
    digest.update(prompt_version.lower().encode("utf-8"))
    return digest.hexdigest()


def _resolve_source_run_id(payload: RepoFileSummaryRunCreateRequest) -> str:
    """Return normalized source run id from request payload."""

    if payload.source_run_id:
        return payload.source_run_id
    raise RepoFileSummaryError("Provide one of source_run_id or repo_run_id")


def _classify_file_summary_failure(exc: Exception) -> tuple[str, str]:
    """Return stable diagnostic code/message pair for file-summary failures."""

    raw = str(exc).lower()
    if isinstance(exc, AgentProtocolError) or "thought_signature" in raw:
        return "thought_signature_missing", "summary_file_summary_agent_protocol_failed"
    if isinstance(exc, asyncio.TimeoutError):
        return "agent_timeout", "summary_file_summary_agent_timeout"
    if "recursion limit" in raw or "graphrecursionerror" in raw:
        return "recursion_limit", "summary_file_summary_agent_recursion_limit"
    return "summary_failed", "summary_file_summary_failed"
