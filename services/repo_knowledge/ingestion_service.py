from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from infrastructure.models import RepoFileSummaryRunRecord, RepoRunRecord
from infrastructure.repositories import (
    RepoChunkRepository,
    RepoDiagnosticRepository,
    RepoEdgeRepository,
    RepoFileSummaryRunRepository,
    RepoRunRepository,
    RepoSnapshotRepository,
    RepoSubjectRepository,
)
from schemas.repo_knowledge import RepoRunCreateRequest
from services.repo_knowledge.chunking_service import RepoChunkingService
from services.repo_knowledge.import_resolution import (
    python_import_candidates,
    ts_js_import_candidates,
)
from services.repo_knowledge.parsing.parser_registry import ParserRegistry
from services.repo_knowledge.parsing.types import ParsedEdge, ParsedFileGraph
from services.repo_knowledge.path_input_normalization import coerce_local_source_path
from services.repo_knowledge.sources.git_clone_source import GitCloneSourceAdapter
from services.repo_knowledge.sources.local_path_source import LocalPathSourceAdapter

logger = logging.getLogger(__name__)

MAX_EXTERNAL_REF_CHARS = 256


class RepoIngestionError(Exception):
    """Raised when a run request cannot be accepted."""


@dataclass(slots=True)
class FileReadResult:
    """Decoded file payload and metadata."""

    text: str | None
    encoding: str | None
    size_bytes: int | None
    line_count: int | None
    content_hash: str | None
    skip_reason: str | None


@dataclass(slots=True)
class RunCounters:
    """Mutable counters tracked while processing a run."""

    files_seen: int = 0
    files_ingested: int = 0
    files_skipped: int = 0
    chunks_written: int = 0
    parse_success_count: int = 0
    parse_failed_count: int = 0
    edge_count_file: int = 0
    edge_count_symbol: int = 0


class RepoKnowledgeService:
    """Application service for repo-knowledge API operations."""

    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.run_repo = RepoRunRepository(session)
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.snapshot_repo = RepoSnapshotRepository(session)
        self.edge_repo = RepoEdgeRepository(session)

    async def create_run(self, payload: RepoRunCreateRequest) -> RepoRunRecord:
        settings = get_settings()
        logger.info(
            "Create repo run request tenant=%s user=%s source_type=%s source_path=%s repo_address=%s force_reingest=%s",
            self.tenant_id,
            self.user_id,
            payload.source_type,
            payload.source_path,
            payload.repo_address,
            payload.force_reingest,
        )

        if payload.source_type == "git_url":
            source_locator = payload.source_path.strip()
            if not (source_locator.startswith("https://") or source_locator.startswith("git@")):
                raise RepoIngestionError("git_url source_path must start with https:// or git@")
            repo_address = payload.repo_address or _derive_repo_address_from_url(source_locator)
        else:
            validated_path = _validate_local_source_path(
                source_path=payload.source_path,
                allowed_roots=settings.REPO_INGEST_ALLOWED_ROOTS_LIST,
            )
            source_locator = str(validated_path)
            repo_address = payload.repo_address or source_locator

        include_extensions = _normalize_extensions(
            payload.include_extensions or settings.REPO_INGEST_ALLOWED_EXTENSIONS_LIST
        )
        if not include_extensions:
            logger.error("Create repo run failed: include_extensions resolved to empty set")
            raise RepoIngestionError("No include extensions configured for repository ingestion")

        exclude_globs = [item.strip() for item in (payload.exclude_globs or []) if item and item.strip()]

        run = await self.run_repo.create(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            source_type=payload.source_type,
            source_locator=source_locator,
            repo_address=repo_address,
            include_extensions=",".join(sorted(include_extensions)),
            exclude_globs="\n".join(exclude_globs),
        )
        logger.info(
            "Create repo run succeeded run_id=%s source_locator=%s include_ext_count=%s exclude_glob_count=%s",
            run.id,
            run.source_locator,
            len(include_extensions),
            len(exclude_globs),
        )
        return run

    async def get_run_status(self, *, run_id: str) -> RepoRunRecord | None:
        logger.debug("Fetch repo run status run_id=%s tenant=%s user=%s", run_id, self.tenant_id, self.user_id)
        return await self.run_repo.get_scoped(run_id, tenant_id=self.tenant_id, user_id=self.user_id)

    async def list_runs(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None,
    ) -> tuple[list[RepoRunRecord], dict[str, list[RepoFileSummaryRunRecord]]]:
        logger.debug(
            "List repo runs requested tenant=%s user=%s limit=%s offset=%s status=%s",
            self.tenant_id,
            self.user_id,
            limit,
            offset,
            status,
        )
        runs = await self.run_repo.list_scoped(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            limit=limit,
            offset=offset,
            status=status,
        )
        source_run_ids = [run.id for run in runs]
        file_summary_runs_by_source = await self.file_summary_run_repo.list_for_sources(
            source_run_ids=source_run_ids,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            limit_per_source=20,
        )
        return runs, file_summary_runs_by_source

    async def list_files(
        self,
        *,
        run_id: str,
        limit: int,
        offset: int,
        ingest_status: str | None,
    ):
        logger.debug(
            "List repo run files run_id=%s tenant=%s user=%s limit=%s offset=%s ingest_status=%s",
            run_id,
            self.tenant_id,
            self.user_id,
            limit,
            offset,
            ingest_status,
        )
        run = await self.run_repo.get_scoped(run_id, tenant_id=self.tenant_id, user_id=self.user_id)
        if run is None:
            return None
        return await self.snapshot_repo.list_for_run(
            run_id=run_id,
            limit=limit,
            offset=offset,
            ingest_status=ingest_status,
        )

    async def list_edges(
        self,
        *,
        run_id: str,
        limit: int,
        offset: int,
        edge_type: str | None,
        from_subject_type: str | None,
        to_subject_type: str | None,
        language: str | None,
    ):
        logger.debug(
            "List repo run edges run_id=%s tenant=%s user=%s limit=%s offset=%s edge_type=%s from_type=%s to_type=%s language=%s",
            run_id,
            self.tenant_id,
            self.user_id,
            limit,
            offset,
            edge_type,
            from_subject_type,
            to_subject_type,
            language,
        )
        run = await self.run_repo.get_scoped(run_id, tenant_id=self.tenant_id, user_id=self.user_id)
        if run is None:
            return None
        return await self.edge_repo.list_for_run(
            run_id=run_id,
            limit=limit,
            offset=offset,
            edge_type=edge_type,
            from_subject_type=from_subject_type,
            to_subject_type=to_subject_type,
            language=language,
        )


class RepoIngestionWorker:
    """Background worker that executes queued repository ingestion runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.run_repo = RepoRunRepository(session)
        self.subject_repo = RepoSubjectRepository(session)
        self.snapshot_repo = RepoSnapshotRepository(session)
        self.chunk_repo = RepoChunkRepository(session)
        self.edge_repo = RepoEdgeRepository(session)
        self.diagnostic_repo = RepoDiagnosticRepository(session)

    async def execute(self, *, run_id: str, force_reingest: bool = False) -> None:
        settings = get_settings()
        logger.info(
            "Repo ingestion execute start run_id=%s force_reingest=%s",
            run_id,
            force_reingest,
        )
        run = await self.run_repo.get(run_id)
        if run is None:
            logger.warning("Repo ingestion execute abort: run not found run_id=%s", run_id)
            return
        if run.status not in {"queued", "failed"}:
            logger.info("Skipping run %s with status=%s", run.id, run.status)
            return

        run_id_value = run.id
        await self.run_repo.mark_in_progress(run)
        await self.session.commit()
        logger.info(
            "Repo ingestion marked in_progress run_id=%s repo_address=%s source_type=%s source_locator=%s",
            run_id_value,
            run.repo_address,
            run.source_type,
            run.source_locator,
        )

        counters = RunCounters()
        fingerprint_material: list[str] = []

        include_extensions = _normalize_extensions(
            _split_csv(run.include_extensions) or settings.REPO_INGEST_ALLOWED_EXTENSIONS_LIST
        )
        exclude_globs = _split_lines(run.exclude_globs)
        logger.info(
            "Repo ingestion configuration run_id=%s include_ext=%s exclude_globs=%s excluded_dirs=%s",
            run.id,
            sorted(include_extensions),
            exclude_globs,
            settings.REPO_INGEST_EXCLUDED_DIRS_LIST,
        )

        source_adapter = self._build_source_adapter(
            run=run,
            include_extensions=include_extensions,
            excluded_dirs=set(settings.REPO_INGEST_EXCLUDED_DIRS_LIST),
            exclude_globs=exclude_globs,
        )

        chunking = RepoChunkingService(
            chunk_size=settings.REPO_INGEST_CHUNK_SIZE,
            chunk_overlap=settings.REPO_INGEST_CHUNK_OVERLAP,
        )
        parser_registry = ParserRegistry(enabled_languages=set(settings.REPO_PARSE_LANGUAGES_LIST))
        logger.info(
            "Repo ingestion parser configuration run_id=%s parse_languages=%s ingest_max_bytes=%s parse_max_bytes=%s",
            run_id_value,
            settings.REPO_PARSE_LANGUAGES_LIST,
            settings.REPO_INGEST_MAX_FILE_BYTES,
            settings.REPO_PARSE_MAX_FILE_BYTES,
        )

        try:
            await source_adapter.prepare()
            logger.info("Repo ingestion source prepared run_id=%s", run_id_value)
            files = list(source_adapter.iter_files())
            counters.files_seen = len(files)
            logger.info("Repo ingestion files discovered run_id=%s file_count=%s", run_id_value, counters.files_seen)

            for idx, discovered in enumerate(files, start=1):
                relative_path = discovered.relative_path
                language = ParserRegistry.detect_language(relative_path)
                logger.info(
                    "Repo ingestion processing file run_id=%s index=%s/%s file=%s language=%s",
                    run_id_value,
                    idx,
                    counters.files_seen,
                    relative_path,
                    language,
                )
                file_subject = await self.subject_repo.get_or_create_file(
                    repo_address=run.repo_address,
                    subject_path=relative_path,
                    language=language,
                )
                logger.debug(
                    "Repo ingestion file subject resolved run_id=%s file=%s subject_id=%s",
                    run_id_value,
                    relative_path,
                    file_subject.id,
                )

                read_result = _read_file_for_ingestion(
                    path=discovered.absolute_path,
                    max_file_bytes=settings.REPO_INGEST_MAX_FILE_BYTES,
                )

                if read_result.skip_reason:
                    parse_status = "failed"
                    if read_result.skip_reason == "file_too_large":
                        parse_status = "skipped_too_large"
                    logger.info(
                        "Repo ingestion file skipped run_id=%s file=%s skip_reason=%s size=%s parse_status=%s",
                        run_id_value,
                        relative_path,
                        read_result.skip_reason,
                        read_result.size_bytes,
                        parse_status,
                    )
                    await self.snapshot_repo.upsert(
                        run_id=run.id,
                        subject_id=file_subject.id,
                        size_bytes=read_result.size_bytes,
                        line_count=read_result.line_count,
                        content_hash=read_result.content_hash,
                        encoding=read_result.encoding,
                        ingest_status="skipped",
                        parse_status=parse_status,
                        skip_reason=read_result.skip_reason,
                        parse_error=None,
                        chunk_count=0,
                    )
                    counters.files_skipped += 1
                    await self.session.commit()
                    continue

                assert read_result.text is not None
                extension = Path(relative_path).suffix.lower()
                chunks = chunking.chunk_text(text=read_result.text, extension=extension)
                chunk_count = await self.chunk_repo.replace_for_subject(
                    run_id=run.id,
                    subject_id=file_subject.id,
                    chunks=chunks,
                )
                logger.info(
                    "Repo ingestion chunked file run_id=%s file=%s chunk_count=%s size=%s encoding=%s",
                    run_id_value,
                    relative_path,
                    chunk_count,
                    read_result.size_bytes,
                    read_result.encoding,
                )
                counters.files_ingested += 1
                counters.chunks_written += chunk_count

                parse_status = "pending"
                parse_error: str | None = None
                parser_selection = parser_registry.get_parser(file_path=relative_path)
                logger.debug(
                    "Repo ingestion parser selected run_id=%s file=%s language=%s parser_available=%s",
                    run_id_value,
                    relative_path,
                    parser_selection.language,
                    parser_selection.parser is not None,
                )

                if parser_selection.language == "unknown":
                    parse_status = "unsupported_language"
                    logger.info(
                        "Repo ingestion parse skipped (unsupported language) run_id=%s file=%s",
                        run_id_value,
                        relative_path,
                    )
                elif read_result.size_bytes and read_result.size_bytes > settings.REPO_PARSE_MAX_FILE_BYTES:
                    parse_status = "skipped_too_large"
                    logger.info(
                        "Repo ingestion parse skipped (too large) run_id=%s file=%s size=%s parse_limit=%s",
                        run_id_value,
                        relative_path,
                        read_result.size_bytes,
                        settings.REPO_PARSE_MAX_FILE_BYTES,
                    )
                elif parser_selection.parser is None:
                    parse_status = "failed"
                    parse_error = f"{parser_selection.language} parser unavailable"
                    counters.parse_failed_count += 1
                    logger.warning(
                        "Repo ingestion parser unavailable run_id=%s file=%s language=%s",
                        run_id_value,
                        relative_path,
                        parser_selection.language,
                    )
                else:
                    parse_graph = parser_selection.parser.parse(
                        file_path=relative_path,
                        source_text=read_result.text,
                    )
                    parse_status = "success"
                    counters.parse_success_count += 1
                    logger.info(
                        "Repo ingestion parsed file run_id=%s file=%s symbols=%s edges=%s diagnostics=%s",
                        run_id_value,
                        relative_path,
                        len(parse_graph.symbols),
                        len(parse_graph.edges),
                        len(parse_graph.diagnostics),
                    )
                    await self._persist_parse_graph(
                        run=run,
                        file_subject_id=file_subject.id,
                        relative_path=relative_path,
                        language=parser_selection.language,
                        parse_graph=parse_graph,
                        counters=counters,
                    )

                await self.snapshot_repo.upsert(
                    run_id=run.id,
                    subject_id=file_subject.id,
                    size_bytes=read_result.size_bytes,
                    line_count=read_result.line_count,
                    content_hash=read_result.content_hash,
                    encoding=read_result.encoding,
                    ingest_status="ingested",
                    parse_status=parse_status,
                    skip_reason=None,
                    parse_error=parse_error,
                    chunk_count=chunk_count,
                )
                logger.debug(
                    "Repo ingestion snapshot upserted run_id=%s file=%s parse_status=%s parse_error=%s",
                    run_id_value,
                    relative_path,
                    parse_status,
                    parse_error,
                )

                fingerprint_material.append(
                    f"{relative_path}:{read_result.content_hash or ''}:{read_result.size_bytes or 0}"
                )
                await self.session.commit()
                logger.debug("Repo ingestion file committed run_id=%s file=%s", run_id_value, relative_path)

            fingerprint = _build_fingerprint(fingerprint_material)
            logger.info("Repo ingestion fingerprint computed run_id=%s fingerprint=%s", run_id_value, fingerprint)
            duplicate = await self.run_repo.find_completed_by_fingerprint(
                tenant_id=run.tenant_id,
                user_id=run.user_id,
                source_locator=run.source_locator,
                fingerprint=fingerprint,
                excluding_run_id=run_id_value,
            )
            await self.run_repo.set_counts(
                run,
                files_seen=counters.files_seen,
                files_ingested=counters.files_ingested,
                files_skipped=counters.files_skipped,
                chunks_written=counters.chunks_written,
                parse_success_count=counters.parse_success_count,
                parse_failed_count=counters.parse_failed_count,
                edge_count_file=counters.edge_count_file,
                edge_count_symbol=counters.edge_count_symbol,
            )
            logger.info(
                "Repo ingestion counters finalized run_id=%s files_seen=%s files_ingested=%s files_skipped=%s chunks_written=%s parse_success=%s parse_failed=%s edge_file=%s edge_symbol=%s",
                run_id_value,
                counters.files_seen,
                counters.files_ingested,
                counters.files_skipped,
                counters.chunks_written,
                counters.parse_success_count,
                counters.parse_failed_count,
                counters.edge_count_file,
                counters.edge_count_symbol,
            )
            should_mark_duplicate = _should_mark_run_skipped_duplicate(
                duplicate_found=duplicate is not None,
                force_reingest=force_reingest,
            )
            if should_mark_duplicate:
                await self.run_repo.mark_skipped_duplicate(run, fingerprint=fingerprint)
                logger.info("Repo ingestion completed as duplicate run_id=%s", run_id_value)
            else:
                await self.run_repo.mark_completed(run, fingerprint=fingerprint)
                logger.info(
                    "Repo ingestion completed run_id=%s force_reingest=%s duplicate_found=%s",
                    run_id_value,
                    force_reingest,
                    duplicate is not None,
                )
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            logger.exception("Repository ingestion run failed run_id=%s", run_id_value)
            failed_run = await self.run_repo.get(run_id_value)
            if failed_run:
                await self.run_repo.mark_failed(failed_run, error_message=str(exc))
                await self.session.commit()
                logger.error("Repo ingestion marked failed run_id=%s error=%s", run_id_value, exc)
        finally:
            await source_adapter.cleanup()
            logger.info("Repo ingestion source cleanup complete run_id=%s", run_id_value)

    def _build_source_adapter(
        self,
        *,
        run: RepoRunRecord,
        include_extensions: set[str],
        excluded_dirs: set[str],
        exclude_globs: list[str],
    ):
        if run.source_type == "local_path":
            logger.debug("Repo ingestion using LocalPathSourceAdapter run_id=%s", run.id)
            return LocalPathSourceAdapter(
                source_path=run.source_locator,
                include_extensions=include_extensions,
                excluded_dirs=excluded_dirs,
                exclude_globs=exclude_globs,
            )
        if run.source_type == "git_url":
            logger.debug("Repo ingestion using GitCloneSourceAdapter run_id=%s", run.id)
            return GitCloneSourceAdapter(
                source_path=run.source_locator,
                include_extensions=include_extensions,
                excluded_dirs=excluded_dirs,
                exclude_globs=exclude_globs,
            )
        raise RepoIngestionError(f"Unsupported source_type: {run.source_type}")

    async def _persist_parse_graph(
        self,
        *,
        run: RepoRunRecord,
        file_subject_id: str,
        relative_path: str,
        language: str,
        parse_graph: ParsedFileGraph,
        counters: RunCounters,
    ) -> None:
        local_symbols_by_qual: dict[str, str] = {}
        local_symbols_by_name: dict[str, str] = {}
        logger.debug(
            "Persist parse graph begin run_id=%s file=%s symbols=%s edges=%s diagnostics=%s",
            run.id,
            relative_path,
            len(parse_graph.symbols),
            len(parse_graph.edges),
            len(parse_graph.diagnostics),
        )

        for symbol in parse_graph.symbols:
            symbol_subject = await self.subject_repo.get_or_create_symbol(
                repo_address=run.repo_address,
                subject_path=relative_path,
                language=language,
                subject_type=symbol.subject_type,
                symbol_name=symbol.symbol_name,
                symbol_qualname=symbol.symbol_qualname,
            )
            local_symbols_by_qual[symbol.symbol_qualname] = symbol_subject.id
            local_symbols_by_name[symbol.symbol_name] = symbol_subject.id

        edge_rows: list[dict] = []
        runtime_diagnostics: list[dict] = []
        for edge in parse_graph.edges:
            from_subject_id = await self._resolve_from_subject(
                run=run,
                file_subject_id=file_subject_id,
                edge=edge,
                local_symbols_by_qual=local_symbols_by_qual,
                local_symbols_by_name=local_symbols_by_name,
            )
            target_resolution = await self._resolve_to_subject(
                run=run,
                file_subject_id=file_subject_id,
                current_file=relative_path,
                language=language,
                edge=edge,
                local_symbols_by_qual=local_symbols_by_qual,
                local_symbols_by_name=local_symbols_by_name,
                runtime_diagnostics=runtime_diagnostics,
            )
            if target_resolution is None:
                continue
            to_subject_id, is_external_target = target_resolution
            edge_rows.append(
                {
                    "run_id": run.id,
                    "from_subject_id": from_subject_id,
                    "to_subject_id": to_subject_id,
                    "edge_type": edge.edge_type,
                    "line": edge.line,
                    "column": edge.column,
                    "evidence": edge.evidence,
                    "is_external_target": is_external_target,
                }
            )

        if edge_rows:
            unique_edge_rows = _dedupe_edge_rows(edge_rows)
            deduped_count = len(edge_rows) - len(unique_edge_rows)
            if deduped_count:
                logger.debug(
                    "Persist parse graph removed duplicate edges run_id=%s file=%s removed=%s",
                    run.id,
                    relative_path,
                    deduped_count,
                )

            await self.edge_repo.create_many(unique_edge_rows)
            file_edges = sum(1 for edge in unique_edge_rows if edge["edge_type"] in {"imports", "exports"})
            counters.edge_count_file += file_edges
            counters.edge_count_symbol += len(unique_edge_rows) - file_edges
            logger.debug(
                "Persist parse graph edges stored run_id=%s file=%s edge_rows=%s file_edges=%s symbol_edges=%s",
                run.id,
                relative_path,
                len(unique_edge_rows),
                file_edges,
                len(unique_edge_rows) - file_edges,
            )

        diagnostics = [
            {
                "run_id": run.id,
                "subject_id": file_subject_id,
                "language": language,
                "severity": diagnostic.severity,
                "message": diagnostic.message,
                "line": diagnostic.line,
                "column": diagnostic.column,
            }
            for diagnostic in parse_graph.diagnostics
        ]
        diagnostics.extend(runtime_diagnostics)
        if diagnostics:
            await self.diagnostic_repo.create_many(diagnostics)
            logger.debug(
                "Persist parse graph diagnostics stored run_id=%s file=%s diagnostics=%s",
                run.id,
                relative_path,
                len(diagnostics),
            )

    async def _resolve_from_subject(
        self,
        *,
        run: RepoRunRecord,
        file_subject_id: str,
        edge: ParsedEdge,
        local_symbols_by_qual: dict[str, str],
        local_symbols_by_name: dict[str, str],
    ) -> str:
        if not edge.from_symbol_ref:
            return file_subject_id

        from_id = local_symbols_by_qual.get(edge.from_symbol_ref)
        if from_id:
            return from_id

        from_id = local_symbols_by_name.get(edge.from_symbol_ref)
        if from_id:
            return from_id

        found = await self.subject_repo.find_symbol_by_qualname(
            repo_address=run.repo_address,
            symbol_qualname=edge.from_symbol_ref,
        )
        if found:
            return found.id

        found = await self.subject_repo.find_symbol_by_name(
            repo_address=run.repo_address,
            symbol_name=edge.from_symbol_ref.split(".")[-1],
        )
        if found:
            return found.id

        return file_subject_id

    async def _resolve_to_subject(
        self,
        *,
        run: RepoRunRecord,
        file_subject_id: str,
        current_file: str,
        language: str,
        edge: ParsedEdge,
        local_symbols_by_qual: dict[str, str],
        local_symbols_by_name: dict[str, str],
        runtime_diagnostics: list[dict],
    ) -> tuple[str, bool] | None:
        if edge.edge_type == "exports" and not edge.to_symbol_ref:
            return file_subject_id, False

        # file-level import edge target resolution
        if edge.edge_type in {"imports", "exports"} and edge.to_file_or_external:
            file_target = await _resolve_import_target(
                subject_repo=self.subject_repo,
                repo_address=run.repo_address,
                language=language,
                current_file=current_file,
                ref=edge.to_file_or_external,
            )
            if file_target:
                return file_target.id, False

        if edge.to_symbol_ref:
            to_id = local_symbols_by_qual.get(edge.to_symbol_ref)
            if to_id:
                return to_id, False
            to_id = local_symbols_by_name.get(edge.to_symbol_ref)
            if to_id:
                return to_id, False

            found = await self.subject_repo.find_symbol_by_qualname(
                repo_address=run.repo_address,
                symbol_qualname=edge.to_symbol_ref,
            )
            if found:
                return found.id, False

            found = await self.subject_repo.find_symbol_by_name(
                repo_address=run.repo_address,
                symbol_name=edge.to_symbol_ref.split(".")[-1],
            )
            if found:
                return found.id, False

        external_ref_raw = _select_external_reference(edge=edge)
        external_ref, hashed = _compact_external_reference(external_ref_raw)
        if hashed:
            runtime_diagnostics.append(
                {
                    "run_id": run.id,
                    "subject_id": file_subject_id,
                    "language": language,
                    "severity": "warning",
                    "message": (
                        "external_ref_hashed_due_to_length "
                        f"edge_type={edge.edge_type} "
                        f"length={len(external_ref_raw)} "
                        f"preview={_diagnostic_preview(external_ref_raw)}"
                    ),
                    "line": edge.line,
                    "column": edge.column,
                }
            )

        try:
            external_subject = await self.subject_repo.get_or_create_external(
                repo_address=run.repo_address,
                external_ref=external_ref,
            )
            return external_subject.id, True
        except Exception as exc:
            logger.warning(
                "Skipping unresolved external edge due to subject insert failure run_id=%s file=%s edge_type=%s error=%s",
                run.id,
                current_file,
                edge.edge_type,
                exc,
            )
            runtime_diagnostics.append(
                {
                    "run_id": run.id,
                    "subject_id": file_subject_id,
                    "language": language,
                    "severity": "warning",
                    "message": (
                        "external_subject_create_failed "
                        f"edge_type={edge.edge_type} "
                        f"error={_truncate_text(str(exc), max_chars=220)} "
                        f"ref={_diagnostic_preview(external_ref_raw)}"
                    ),
                    "line": edge.line,
                    "column": edge.column,
                }
            )
            return None


def _should_mark_run_skipped_duplicate(*, duplicate_found: bool, force_reingest: bool) -> bool:
    """Return whether ingestion should finalize as skipped-duplicate."""

    if force_reingest:
        return False
    return duplicate_found


def _build_fingerprint(material: list[str]) -> str:
    digest = hashlib.sha256()
    for line in sorted(material):
        digest.update(line.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _select_external_reference(*, edge: ParsedEdge) -> str:
    candidates: list[str | None]
    if edge.edge_type in {"calls", "references", "inherits"}:
        candidates = [edge.to_symbol_ref, edge.to_file_or_external]
    else:
        candidates = [edge.to_file_or_external, edge.to_symbol_ref]

    for item in candidates:
        normalized = _normalize_external_reference(item)
        if normalized:
            return normalized
    return "unknown"


def _normalize_external_reference(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized or None


def _compact_external_reference(raw_reference: str) -> tuple[str, bool]:
    if len(raw_reference) <= MAX_EXTERNAL_REF_CHARS:
        return raw_reference, False

    digest = hashlib.sha256(raw_reference.encode("utf-8")).hexdigest()
    return f"ext_sha256:{digest}", True


def _diagnostic_preview(value: str, *, max_chars: int = 100) -> str:
    return _truncate_text(value, max_chars=max_chars)


def _truncate_text(value: str, *, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}..."


def _normalize_extensions(items: list[str]) -> set[str]:
    normalized: set[str] = set()
    for item in items:
        ext = item.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.add(ext)
    return normalized


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _split_lines(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.splitlines() if item.strip()]


def _dedupe_edge_rows(edge_rows: list[dict]) -> list[dict]:
    """Remove duplicate edge rows that would violate the repo edge uniqueness constraint."""
    unique_rows: list[dict] = []
    seen_keys: set[tuple[str, str, str, str, int | None, int | None]] = set()

    for edge in edge_rows:
        key = (
            str(edge["run_id"]),
            str(edge["from_subject_id"]),
            str(edge["to_subject_id"]),
            str(edge["edge_type"]),
            edge.get("line"),
            edge.get("column"),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_rows.append(edge)

    return unique_rows


def _derive_repo_address_from_url(url: str) -> str:
    """Derive a repo address from a git URL (e.g. 'https://github.com/user/repo' → 'github.com/user/repo')."""
    cleaned = url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    if cleaned.startswith("https://"):
        return cleaned[len("https://"):]
    if cleaned.startswith("http://"):
        return cleaned[len("http://"):]
    if cleaned.startswith("git@"):
        # git@github.com:user/repo → github.com/user/repo
        return cleaned[len("git@"):].replace(":", "/", 1)
    return cleaned


def _validate_local_source_path(*, source_path: str, allowed_roots: list[str]) -> Path:
    normalized_source_path = coerce_local_source_path(source_path)
    path = Path(normalized_source_path).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise RepoIngestionError("source_path must exist and be a directory")

    if not allowed_roots:
        return path

    allowed_root_paths = [Path(root).expanduser().resolve() for root in allowed_roots]
    for root in allowed_root_paths:
        if root == path or root in path.parents:
            return path
    raise RepoIngestionError("source_path is outside configured REPO_INGEST_ALLOWED_ROOTS")


def _read_file_for_ingestion(*, path: Path, max_file_bytes: int) -> FileReadResult:
    try:
        raw = path.read_bytes()
    except Exception as exc:
        logger.warning("Read file failed path=%s error=%s", path, exc)
        return FileReadResult(
            text=None,
            encoding=None,
            size_bytes=None,
            line_count=None,
            content_hash=None,
            skip_reason=f"read_failed:{exc}",
        )

    size_bytes = len(raw)
    if size_bytes > max_file_bytes:
        logger.info("Read file skipped (too large) path=%s size=%s max=%s", path, size_bytes, max_file_bytes)
        return FileReadResult(
            text=None,
            encoding=None,
            size_bytes=size_bytes,
            line_count=None,
            content_hash=hashlib.sha256(raw).hexdigest(),
            skip_reason="file_too_large",
        )

    if b"\x00" in raw[:4096]:
        logger.info("Read file skipped (binary signature) path=%s", path)
        return FileReadResult(
            text=None,
            encoding=None,
            size_bytes=size_bytes,
            line_count=None,
            content_hash=hashlib.sha256(raw).hexdigest(),
            skip_reason="binary_file",
        )

    encoding = "utf-8"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        encoding = "latin-1"
        text = raw.decode("latin-1", errors="ignore")
        logger.debug("Read file decoded with latin-1 fallback path=%s", path)

    line_count = text.count("\n") + 1 if text else 0
    return FileReadResult(
        text=text,
        encoding=encoding,
        size_bytes=size_bytes,
        line_count=line_count,
        content_hash=hashlib.sha256(raw).hexdigest(),
        skip_reason=None,
    )


async def _resolve_import_target(
    *,
    subject_repo: RepoSubjectRepository,
    repo_address: str,
    language: str,
    current_file: str,
    ref: str,
):
    if language == "python":
        candidates = python_import_candidates(current_file=current_file, reference=ref)
    elif language in {"typescript", "javascript"}:
        candidates = ts_js_import_candidates(current_file=current_file, reference=ref)
    else:
        candidates = []

    for candidate in candidates:
        found = await subject_repo.find_file_by_path(repo_address=repo_address, subject_path=candidate)
        if found:
            return found
    return None
