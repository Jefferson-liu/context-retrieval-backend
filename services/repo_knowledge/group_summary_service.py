from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from infrastructure.models import RepoGroupSummaryRunRecord
from infrastructure.repositories import (
    RepoEdgeRepository,
    RepoFileSummaryRunRepository,
    RepoFullSummaryRepository,
    RepoFullSummaryRunRepository,
    RepoGroupSummaryDiagnosticRepository,
    RepoGroupSummaryRepository,
    RepoGroupSummaryRunRepository,
    RepoRunRepository,
    RepoSummaryGroupRepository,
    RepoFileSummaryRepository,
)
from schemas.repo_knowledge_group_summary import RepoGroupSummaryRunCreateRequest
from services.repo_knowledge.group_summarization.errors import TraceableLLMError
from services.repo_knowledge.group_summarization.architecture_merger import (
    ArchitectureMergeInput,
    ArchitectureSegmentArtifact,
    RepoArchitectureMerger,
)
from services.repo_knowledge.group_summarization.group_summarizer import RepoGroupSummarizer
from services.repo_knowledge.group_summarization.types import GroupMemberEvidence, GroupSummaryInput
from services.repo_knowledge.grouping import AdaptiveDependencyRepoManager, GroupFileEdge, GroupFileNode
from services.repo_knowledge.summarization.model_factory import (
    SummaryModelFactoryError,
    create_summary_chat_model,
)

logger = logging.getLogger(__name__)

GEMINI_PROVIDER = "gemini"
GEMINI_MODEL = "gemini-2.5-flash"


class RepoGroupSummaryError(Exception):
    """Raised when a repo-manager architecture run request cannot be accepted."""


@dataclass(slots=True)
class GroupSummaryCounters:
    """Mutable counters tracked while processing one repo-manager architecture run."""

    groups_seen: int = 0
    groups_summarized: int = 0
    groups_failed: int = 0
    members_seen: int = 0


class RepoKnowledgeGroupSummaryService:
    """Application service for repo-manager architecture run APIs."""

    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.run_repo = RepoRunRepository(session)
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.group_summary_run_repo = RepoGroupSummaryRunRepository(session)
        self.summary_group_repo = RepoSummaryGroupRepository(session)

    async def create_group_summary_run(
        self,
        payload: RepoGroupSummaryRunCreateRequest,
    ) -> RepoGroupSummaryRunRecord:
        settings = get_settings()

        file_summary_run = await self.file_summary_run_repo.get_scoped(
            payload.source_file_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if file_summary_run is None:
            raise RepoGroupSummaryError("source_file_summary_run_id not found")
        if file_summary_run.status != "completed":
            raise RepoGroupSummaryError("source_file_summary_run_id must be completed")

        source_run = await self.run_repo.get_scoped(
            file_summary_run.source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if source_run is None:
            raise RepoGroupSummaryError("source_run_id not found")
        if source_run.status not in {"completed", "skipped_duplicate"}:
            raise RepoGroupSummaryError("source_run_id must be completed or skipped_duplicate")

        run_fingerprint = _build_group_summary_fingerprint(
            source_run_id=source_run.id,
            source_file_summary_run_id=file_summary_run.id,
            prompt_version=settings.REPO_GROUP_SUMMARY_PROMPT_VERSION,
            merge_prompt_version=settings.REPO_ARCHITECTURE_MERGE_PROMPT_VERSION,
            max_group_tokens=settings.REPO_MANAGER_MAX_GROUP_TOKENS,
            representative_count=settings.REPO_GROUP_REPRESENTATIVE_COUNT,
            model_provider=GEMINI_PROVIDER,
            model_name=GEMINI_MODEL,
        )

        if not payload.force_resummarize:
            existing = await self.group_summary_run_repo.find_completed_by_fingerprint(
                source_run_id=source_run.id,
                source_file_summary_run_id=file_summary_run.id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                run_fingerprint=run_fingerprint,
            )
            if existing is not None:
                logger.info(
                    "Reusing completed group-summary run group_summary_run_id=%s source_run_id=%s file_summary_run_id=%s",
                    existing.id,
                    source_run.id,
                    file_summary_run.id,
                )
                return existing

        run = await self.group_summary_run_repo.create(
            source_run_id=source_run.id,
            source_file_summary_run_id=file_summary_run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            run_fingerprint=run_fingerprint,
            prompt_version=settings.REPO_GROUP_SUMMARY_PROMPT_VERSION,
        )
        logger.info(
            "Created group-summary run group_summary_run_id=%s source_run_id=%s file_summary_run_id=%s",
            run.id,
            run.source_run_id,
            run.source_file_summary_run_id,
        )
        return run

    async def get_group_summary_run_status(self, *, group_summary_run_id: str) -> RepoGroupSummaryRunRecord | None:
        return await self.group_summary_run_repo.get_scoped(
            group_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

    async def get_architecture_artifact(self, *, group_summary_run_id: str) -> RepoGroupSummaryRunRecord | None:
        run = await self.group_summary_run_repo.get_scoped(
            group_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if run is None or not run.merged_mermaid_diagram:
            return None
        return run

    async def list_group_summaries(
        self,
        *,
        group_summary_run_id: str,
        limit: int,
        offset: int,
        layer_hint: str | None,
        is_infrastructure: bool | None,
        group_key_prefix: str | None,
        include_members: bool,
    ):
        run = await self.group_summary_run_repo.get_scoped(
            group_summary_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if run is None:
            return None, None, None

        rows = await self.summary_group_repo.list_groups_for_run(
            group_summary_run_id=run.id,
            limit=limit,
            offset=offset,
            layer_hint=layer_hint,
            is_infrastructure=is_infrastructure,
            group_key_prefix=group_key_prefix,
        )
        member_map = None
        if include_members:
            group_ids = [group.group_id for group, _summary in rows]
            member_map = await self.summary_group_repo.list_members_for_groups(
                group_summary_run_id=run.id,
                group_ids=group_ids,
            )
        return run, rows, member_map

    async def latest_group_summaries_for_source_run(
        self,
        *,
        source_run_id: str,
        limit: int,
        offset: int,
        include_members: bool,
    ):
        source_run = await self.run_repo.get_scoped(
            source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if source_run is None:
            return None, None, None

        latest = await self.group_summary_run_repo.latest_completed_for_source(
            source_run_id=source_run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if latest is None:
            return source_run, None, None

        rows = await self.summary_group_repo.list_groups_for_run(
            group_summary_run_id=latest.id,
            limit=limit,
            offset=offset,
            layer_hint=None,
            is_infrastructure=None,
            group_key_prefix=None,
        )
        member_map = None
        if include_members:
            group_ids = [group.group_id for group, _summary in rows]
            member_map = await self.summary_group_repo.list_members_for_groups(
                group_summary_run_id=latest.id,
                group_ids=group_ids,
            )
        return latest, rows, member_map


@dataclass(slots=True)
class GroupSummaryAgentConfig:
    """Tunable agent parameters for repo-manager architecture runs.

    Override at construction time or leave as defaults.
    Env-var overrides from settings are applied in ``from_settings()``.
    """

    # Grouping
    max_group_tokens: int = 5_000
    representative_count: int = 8

    # Segment summarizer
    segment_max_input_chars: int = 26_000
    segment_retry_count: int = 2
    segment_timeout_seconds: int = 60

    # Architecture merger
    merge_max_input_chars: int = 32_000
    merge_retry_count: int = 2
    merge_timeout_seconds: int = 90

    # Model
    model_provider: str = "gemini"
    model_name: str = "gemini-2.5-flash"

    @classmethod
    def from_settings(cls) -> "GroupSummaryAgentConfig":
        """Build config from env-var backed settings, using class defaults as fallbacks."""
        settings = get_settings()
        return cls(
            max_group_tokens=settings.REPO_MANAGER_MAX_GROUP_TOKENS,
            representative_count=settings.REPO_GROUP_REPRESENTATIVE_COUNT,
            segment_max_input_chars=settings.REPO_MANAGER_MAX_INPUT_CHARS,
            segment_retry_count=settings.REPO_MANAGER_RETRY_COUNT,
            segment_timeout_seconds=settings.REPO_MANAGER_TIMEOUT_SECONDS,
            merge_max_input_chars=settings.REPO_ARCHITECTURE_MERGE_MAX_INPUT_CHARS,
            merge_retry_count=settings.REPO_ARCHITECTURE_MERGE_RETRY_COUNT,
            merge_timeout_seconds=settings.REPO_ARCHITECTURE_MERGE_TIMEOUT_SECONDS,
        )


class RepoGroupSummaryWorker:
    """Background worker that executes queued repo-manager architecture runs."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        agent_config: GroupSummaryAgentConfig | None = None,
    ) -> None:
        self.session = session
        self.agent_config = agent_config or GroupSummaryAgentConfig.from_settings()
        self.group_summary_run_repo = RepoGroupSummaryRunRepository(session)
        self.run_repo = RepoRunRepository(session)
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.repo_full_summary_run_repo = RepoFullSummaryRunRepository(session)
        self.repo_full_summary_repo = RepoFullSummaryRepository(session)
        self.summary_repo = RepoFileSummaryRepository(session)
        self.edge_repo = RepoEdgeRepository(session)
        self.summary_group_repo = RepoSummaryGroupRepository(session)
        self.group_summary_repo = RepoGroupSummaryRepository(session)
        self.group_summary_diagnostic_repo = RepoGroupSummaryDiagnosticRepository(session)

    async def execute(self, *, group_summary_run_id: str) -> None:
        settings = get_settings()
        cfg = self.agent_config
        logger.info("Repo group-summary run start group_summary_run_id=%s", group_summary_run_id)

        run = await self.group_summary_run_repo.get(group_summary_run_id)
        if run is None:
            logger.warning("Repo group-summary run abort: run not found group_summary_run_id=%s", group_summary_run_id)
            return
        if run.status not in {"queued", "failed"}:
            logger.info("Skipping group-summary run %s with status=%s", run.id, run.status)
            return

        run_id_value = run.id
        await self.group_summary_run_repo.mark_in_progress(run)
        await self.session.commit()

        source_run = await self.run_repo.get(run.source_run_id)
        if source_run is None:
            await self.group_summary_run_repo.mark_failed(run, error_message="source_run_id not found")
            await self.session.commit()
            return
        if source_run.status not in {"completed", "skipped_duplicate"}:
            await self.group_summary_run_repo.mark_failed(
                run,
                error_message=f"source run has unsupported status: {source_run.status}",
            )
            await self.session.commit()
            return

        file_summary_run = await self.file_summary_run_repo.get(run.source_file_summary_run_id)
        if file_summary_run is None:
            await self.group_summary_run_repo.mark_failed(run, error_message="source_file_summary_run_id not found")
            await self.session.commit()
            return
        if file_summary_run.status != "completed":
            await self.group_summary_run_repo.mark_failed(
                run,
                error_message=f"source file_summary run has unsupported status: {file_summary_run.status}",
            )
            await self.session.commit()
            return

        try:
            chat_model = create_summary_chat_model(
                settings=settings,
                provider_override=cfg.model_provider,
                model_override=cfg.model_name,
            )
        except SummaryModelFactoryError as exc:
            await self.group_summary_run_repo.mark_failed(run, error_message=str(exc))
            await self.session.commit()
            return

        grouper = AdaptiveDependencyRepoManager(
            max_group_tokens=cfg.max_group_tokens,
            representative_count=cfg.representative_count,
        )
        summarizer = RepoGroupSummarizer(
            chat_model=chat_model,
            prompt_version=run.prompt_version,
            max_input_chars=cfg.segment_max_input_chars,
            retry_count=cfg.segment_retry_count,
            timeout_seconds=cfg.segment_timeout_seconds,
        )
        merger = RepoArchitectureMerger(
            chat_model=chat_model,
            max_input_chars=cfg.merge_max_input_chars,
            retry_count=cfg.merge_retry_count,
            timeout_seconds=cfg.merge_timeout_seconds,
        )

        counters = GroupSummaryCounters()
        try:
            summary_rows = await self.summary_repo.list_for_file_summary_all(file_summary_run_id=run.source_file_summary_run_id)
            node_by_id: dict[str, GroupFileNode] = {}
            for summary, subject, _snapshot in summary_rows:
                node_by_id[subject.id] = GroupFileNode(
                    subject_id=subject.id,
                    subject_path=subject.subject_path,
                    language=subject.language,
                    overall_summary=summary.overall_summary,
                    group_function=summary.group_function,
                    important_relationships=list(summary.important_relationships or []),
                )
            file_nodes = sorted(node_by_id.values(), key=lambda item: item.subject_path)

            raw_edges = await self.edge_repo.list_file_edges_for_run(run_id=run.source_run_id)
            file_edges = [
                GroupFileEdge(
                    from_subject_id=edge["from_subject_id"],
                    to_subject_id=edge["to_subject_id"],
                    edge_type=edge["edge_type"],
                )
                for edge in raw_edges
                if edge["from_subject_id"] in node_by_id and edge["to_subject_id"] in node_by_id
            ]

            build_result = grouper.build_groups(file_nodes=file_nodes, file_edges=file_edges)
            counters.groups_seen = len(build_result.groups)
            counters.members_seen = build_result.members_seen
            await self.group_summary_run_repo.set_counts(
                run,
                groups_seen=counters.groups_seen,
                groups_summarized=counters.groups_summarized,
                groups_failed=counters.groups_failed,
                members_seen=counters.members_seen,
            )
            await self.session.commit()

            await self.summary_group_repo.clear_for_run(group_summary_run_id=run.id)

            group_rows: list[dict] = []
            member_rows: list[dict] = []
            for group in build_result.groups:
                group_rows.append(
                    {
                        "group_summary_run_id": run.id,
                        "group_id": group.group_id,
                        "source_run_id": run.source_run_id,
                        "source_file_summary_run_id": run.source_file_summary_run_id,
                        "group_key": group.group_key,
                        "group_label": group.group_label,
                        "layer_hint": group.layer_hint,
                        "member_count": group.member_count,
                        "dependency_neighbor_count": group.dependency_neighbor_count,
                        "is_infrastructure_seed": group.is_infrastructure_seed,
                        "heuristics": group.heuristics,
                    }
                )
                for member in group.members:
                    member_rows.append(
                        {
                            "group_summary_run_id": run.id,
                            "group_id": group.group_id,
                            "subject_id": member.subject_id,
                            "rank": member.rank,
                            "is_representative": member.is_representative,
                            "membership_reason": member.membership_reason,
                        }
                    )
            await self.summary_group_repo.create_groups(group_rows)
            await self.summary_group_repo.create_group_members(member_rows)
            await self.session.commit()

            neighbor_paths = _group_neighbor_paths(
                groups=build_result.groups,
                file_edges=file_edges,
                node_by_id=node_by_id,
            )
            segment_artifacts: list[ArchitectureSegmentArtifact] = []

            # Build all inputs upfront
            group_inputs: list[tuple] = []
            for group in build_result.groups:
                members = sorted(group.members, key=lambda item: item.rank)
                evidence = [
                    GroupMemberEvidence(
                        subject_id=member.subject_id,
                        subject_path=node_by_id[member.subject_id].subject_path,
                        language=node_by_id[member.subject_id].language,
                        overall_summary=node_by_id[member.subject_id].overall_summary,
                        group_function=node_by_id[member.subject_id].group_function,
                        important_relationships=node_by_id[member.subject_id].important_relationships,
                        is_representative=member.is_representative,
                        rank=member.rank,
                    )
                    for member in members
                    if member.subject_id in node_by_id
                ]
                group_inputs.append((group, evidence))

            # Run all LLM summarizations concurrently (no DB access in summarizer)
            sem = asyncio.Semaphore(5)

            async def _summarize_one(group, evidence):
                async with sem:
                    return await summarizer.summarize(
                        payload=GroupSummaryInput(
                            source_run_id=run.source_run_id,
                            source_file_summary_run_id=run.source_file_summary_run_id,
                            group_id=group.group_id,
                            group_key=group.group_key,
                            group_label=group.group_label,
                            layer_hint=group.layer_hint,
                            is_infrastructure_seed=group.is_infrastructure_seed,
                            heuristics=group.heuristics,
                            dependency_neighbor_paths=neighbor_paths.get(group.group_id, []),
                            representative_subject_ids=group.representative_subject_ids,
                            members=evidence,
                        )
                    )

            results = await asyncio.gather(
                *[_summarize_one(group, evidence) for group, evidence in group_inputs],
                return_exceptions=True,
            )

            # Write results to DB sequentially (shared session)
            for (group, _evidence), result in zip(group_inputs, results):
                if isinstance(result, TraceableLLMError):
                    counters.groups_failed += 1
                    await self.group_summary_diagnostic_repo.create(
                        group_summary_run_id=run.id,
                        group_id=group.group_id,
                        severity="error",
                        message=result.message,
                        details={
                            "stage": result.stage,
                            "diagnostic_code": result.diagnostic_code,
                            "group_key": group.group_key,
                            "error": result.details.get("error", str(result)),
                            "error_type": result.details.get("error_type", type(result).__name__),
                            "raw_text": result.raw_text,
                        },
                    )
                elif isinstance(result, Exception):
                    counters.groups_failed += 1
                    await self.group_summary_diagnostic_repo.create(
                        group_summary_run_id=run.id,
                        group_id=group.group_id,
                        severity="error",
                        message="repo_manager_segment_failed",
                        details={
                            "stage": "repo_manager_segment",
                            "diagnostic_code": "repo_manager_segment_runtime_failed",
                            "group_key": group.group_key,
                            "error": str(result),
                            "error_type": type(result).__name__,
                        },
                    )
                else:
                    await self.group_summary_repo.upsert(
                        group_summary_run_id=run.id,
                        group_id=group.group_id,
                        source_run_id=run.source_run_id,
                        source_file_summary_run_id=run.source_file_summary_run_id,
                        name=result.output.name,
                        overall_summary=result.output.overall_summary,
                        business_purpose=result.output.business_purpose,
                        responsibilities=result.output.responsibilities,
                        tags=result.output.tags,
                        representative_subject_ids=result.output.representative_subject_ids,
                        mermaid_diagram=result.output.mermaid_diagram,
                        is_infrastructure=result.output.is_infrastructure,
                        confidence=result.output.confidence,
                        raw_output=result.raw_output,
                        input_hash=result.input_hash,
                    )
                    segment_artifacts.append(
                        ArchitectureSegmentArtifact(
                            group_id=group.group_id,
                            name=result.output.name,
                            overall_summary=result.output.overall_summary,
                            business_purpose=result.output.business_purpose,
                            mermaid_diagram=result.output.mermaid_diagram,
                        )
                    )
                    counters.groups_summarized += 1

            await self.group_summary_run_repo.set_counts(
                run,
                groups_seen=counters.groups_seen,
                groups_summarized=counters.groups_summarized,
                groups_failed=counters.groups_failed,
                members_seen=counters.members_seen,
            )
            await self.session.commit()

            if counters.groups_summarized == 0:
                await self.group_summary_run_repo.mark_failed(
                    run,
                    error_message="No groups were summarized successfully",
                )
            else:
                repo_readme_markdown = await self._load_repo_readme_markdown(
                    source_run_id=run.source_run_id,
                    source_file_summary_run_id=run.source_file_summary_run_id,
                    tenant_id=run.tenant_id,
                    user_id=run.user_id,
                )
                try:
                    merge_result = await merger.summarize(
                        payload=ArchitectureMergeInput(
                            source_run_id=run.source_run_id,
                            source_file_summary_run_id=run.source_file_summary_run_id,
                            repo_readme_markdown=repo_readme_markdown,
                            segment_artifacts=segment_artifacts,
                            prompt_version=settings.REPO_ARCHITECTURE_MERGE_PROMPT_VERSION,
                        )
                    )
                except TraceableLLMError as exc:
                    await self.group_summary_diagnostic_repo.create(
                        group_summary_run_id=run.id,
                        group_id="__architecture_merge__",
                        severity="error",
                        message=exc.message,
                        details={
                            "stage": exc.stage,
                            "diagnostic_code": exc.diagnostic_code,
                            "error": exc.details.get("error", str(exc)),
                            "error_type": exc.details.get("error_type", type(exc).__name__),
                            "raw_text": exc.raw_text,
                        },
                    )
                    await self.group_summary_run_repo.mark_failed(
                        run,
                        error_message=f"{exc.message}:{exc.diagnostic_code}",
                    )
                    await self.session.commit()
                    return
                await self.group_summary_run_repo.set_architecture_artifact(
                    run,
                    architecture_overview=merge_result.output.overall_summary,
                    merged_mermaid_diagram=merge_result.output.mermaid_diagram,
                    merge_raw_output=merge_result.raw_output,
                )
                await self.group_summary_run_repo.mark_completed(run)
            await self.session.commit()
        except Exception as exc:  # pragma: no cover - run-level failures
            await self.session.rollback()
            logger.exception("Repo group-summary run failed group_summary_run_id=%s", run_id_value)
            failed = await self.group_summary_run_repo.get(run_id_value)
            if failed:
                await self.group_summary_run_repo.mark_failed(failed, error_message=str(exc))
                await self.session.commit()

    async def _load_repo_readme_markdown(
        self,
        *,
        source_run_id: str,
        source_file_summary_run_id: str,
        tenant_id: str,
        user_id: str,
    ) -> str:
        run = await self.repo_full_summary_run_repo.latest_for_source_file_summary(
            source_run_id=source_run_id,
            source_file_summary_run_id=source_file_summary_run_id,
            tenant_id=tenant_id,
            user_id=user_id,
            statuses=["completed"],
        )
        if run is None:
            return ""
        artifact = await self.repo_full_summary_repo.get_for_run(repo_full_summary_run_id=run.id)
        if artifact is None:
            return ""
        return artifact.readme_markdown


def _group_neighbor_paths(
    *,
    groups,
    file_edges: list[GroupFileEdge],
    node_by_id: dict[str, GroupFileNode],
) -> dict[str, list[str]]:
    subject_to_group = {
        member.subject_id: group.group_id
        for group in groups
        for member in group.members
    }
    bucket: dict[str, set[str]] = {group.group_id: set() for group in groups}
    for edge in file_edges:
        from_group = subject_to_group.get(edge.from_subject_id)
        to_group = subject_to_group.get(edge.to_subject_id)
        if from_group is None or to_group is None or from_group == to_group:
            continue

        to_node = node_by_id.get(edge.to_subject_id)
        from_node = node_by_id.get(edge.from_subject_id)
        if to_node:
            bucket[from_group].add(to_node.subject_path)
        if from_node:
            bucket[to_group].add(from_node.subject_path)

    return {group_id: sorted(paths)[:20] for group_id, paths in bucket.items()}


def _build_group_summary_fingerprint(
    *,
    source_run_id: str,
    source_file_summary_run_id: str,
    prompt_version: str,
    merge_prompt_version: str,
    max_group_tokens: int,
    representative_count: int,
    model_provider: str,
    model_name: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(source_run_id.encode("utf-8"))
    digest.update(b"|")
    digest.update(source_file_summary_run_id.encode("utf-8"))
    digest.update(b"|")
    digest.update(prompt_version.lower().encode("utf-8"))
    digest.update(b"|")
    digest.update(merge_prompt_version.lower().encode("utf-8"))
    digest.update(b"|")
    digest.update(str(max_group_tokens).encode("utf-8"))
    digest.update(b"|")
    digest.update(str(representative_count).encode("utf-8"))
    digest.update(b"|")
    digest.update(model_provider.lower().encode("utf-8"))
    digest.update(b"|")
    digest.update(model_name.lower().encode("utf-8"))
    return digest.hexdigest()
