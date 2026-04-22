from __future__ import annotations

import fnmatch
import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import (
    RepoEmbeddingRunRecord,
    RepoFileChunkRecord,
    RepoFileSummaryRunRecord,
    RepoFullSummaryRunRecord,
    RepoGroupSummaryRunRecord,
    RepoRunRecord,
    RepoSubjectRecord,
)
from infrastructure.repositories import (
    RepoChunkRepository,
    RepoEdgeRepository,
    RepoEmbeddingRepository,
    RepoEmbeddingRunRepository,
    RepoFileSummaryRunRepository,
    RepoFullSummaryRepository,
    RepoFullSummaryRunRepository,
    RepoGroupSummaryRunRepository,
    RepoRunRepository,
    RepoSnapshotRepository,
    RepoSubjectRepository,
    RepoSummaryGroupRepository,
    RepoFileSummaryRepository,
)


class RepoKnowledgeMcpServiceError(Exception):
    """Raised when MCP tool requests cannot be fulfilled."""


class RepoKnowledgeMcpService:
    """Read-focused service used by MCP tools for repository knowledge data."""

    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.run_repo = RepoRunRepository(session)
        self.snapshot_repo = RepoSnapshotRepository(session)
        self.chunk_repo = RepoChunkRepository(session)
        self.subject_repo = RepoSubjectRepository(session)
        self.edge_repo = RepoEdgeRepository(session)
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.summary_repo = RepoFileSummaryRepository(session)
        self.embedding_run_repo = RepoEmbeddingRunRepository(session)
        self.embedding_repo = RepoEmbeddingRepository(session)
        self.group_summary_run_repo = RepoGroupSummaryRunRepository(session)
        self.summary_group_repo = RepoSummaryGroupRepository(session)
        self.full_summary_run_repo = RepoFullSummaryRunRepository(session)
        self.full_summary_repo = RepoFullSummaryRepository(session)

    async def get_run_overview(self, *, run_id: str) -> dict:
        """Return one scoped run plus latest file_summary/embedding/repo-manager metadata."""
        run = await self._get_scoped_run(run_id)
        latest_file_summary = await self.file_summary_run_repo.latest_completed_for_source(
            source_run_id=run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        latest_embedding = await self.embedding_run_repo.latest_completed_for_source(
            source_run_id=run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        latest_repo_manager = await self.group_summary_run_repo.latest_completed_for_source(
            source_run_id=run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        return {
            "run": self._serialize_run(run),
            "latest_file_summary_run": self._serialize_file_summary_run(latest_file_summary),
            "latest_embedding_run": self._serialize_embedding_run(latest_embedding),
            "latest_repo_manager_run": self._serialize_repo_manager_run(latest_repo_manager),
        }

    async def list_runs(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None,
    ) -> dict:
        """Return scoped ingestion runs so an agent can pick the right repo/run first."""
        runs = await self.run_repo.list_scoped(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            limit=limit,
            offset=offset,
            status=status,
        )
        return {
            "limit": limit,
            "offset": offset,
            "status": status,
            "items": [self._serialize_run(run) for run in runs],
        }

    async def list_files(
        self,
        *,
        run_id: str,
        limit: int,
        offset: int,
        ingest_status: str | None,
    ) -> dict:
        """Return run-scoped file snapshots for MCP inspection."""
        run = await self._get_scoped_run(run_id)
        rows = await self.snapshot_repo.list_for_run(
            run_id=run.id,
            limit=limit,
            offset=offset,
            ingest_status=ingest_status,
        )
        return {
            "run_id": run.id,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "run_id": snapshot.run_id,
                    "subject_id": subject.id,
                    "subject_path": subject.subject_path,
                    "subject_type": subject.subject_type,
                    "language": subject.language,
                    "size_bytes": snapshot.size_bytes,
                    "line_count": snapshot.line_count,
                    "content_hash": snapshot.content_hash,
                    "ingest_status": snapshot.ingest_status,
                    "parse_status": snapshot.parse_status,
                    "skip_reason": snapshot.skip_reason,
                    "parse_error": snapshot.parse_error,
                    "chunk_count": snapshot.chunk_count,
                }
                for snapshot, subject in rows
            ],
        }

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
    ) -> dict:
        """Return run-scoped dependency edges for MCP inspection."""
        run = await self._get_scoped_run(run_id)
        rows = await self.edge_repo.list_for_run(
            run_id=run.id,
            limit=limit,
            offset=offset,
            edge_type=edge_type,
            from_subject_type=from_subject_type,
            to_subject_type=to_subject_type,
            language=language,
        )
        return {
            "run_id": run.id,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "run_id": edge.run_id,
                    "from_subject_id": edge.from_subject_id,
                    "to_subject_id": edge.to_subject_id,
                    "from_subject_type": from_subject.subject_type,
                    "to_subject_type": to_subject.subject_type,
                    "from_subject_path": from_subject.subject_path,
                    "to_subject_path": to_subject.subject_path,
                    "edge_type": edge.edge_type,
                    "line": edge.line,
                    "column": edge.column,
                    "evidence": edge.evidence,
                    "is_external_target": edge.is_external_target,
                }
                for edge, from_subject, to_subject in rows
            ],
        }

    async def list_summaries(
        self,
        *,
        run_id: str | None = None,
        file_summary_run_id: str | None,
        limit: int,
        offset: int,
        language: str | None,
        parse_status: str | None,
        subject_path_prefix: str | None,
    ) -> dict:
        """Return summarized files for a run using explicit or latest file_summary run."""
        run = await self._get_scoped_run(run_id)
        file_summary_run = await self._resolve_file_summary_run(
            run=run,
            file_summary_run_id=file_summary_run_id,
        )
        if file_summary_run is None:
            return {
                "run_id": run.id,
                "file_summary_run_id": None,
                "limit": limit,
                "offset": offset,
                "items": [],
            }

        rows = await self.summary_repo.list_for_file_summary(
            file_summary_run_id=file_summary_run.id,
            source_run_id=run.id,
            limit=limit,
            offset=offset,
            language=language,
            parse_status=parse_status,
            subject_path_prefix=subject_path_prefix,
        )
        return {
            "run_id": run.id,
            "file_summary_run_id": file_summary_run.id,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "subject_id": subject.id,
                    "subject_path": subject.subject_path,
                    "language": subject.language,
                    "parse_status": snapshot.parse_status if snapshot else None,
                    "overall_summary": summary.overall_summary,
                    "file_cluster": list(summary.file_cluster),
                    "important_relationships": list(summary.important_relationships),
                    "group_function": summary.group_function,
                    "updated_at": summary.updated_at.isoformat() if summary.updated_at else None,
                }
                for summary, subject, snapshot in rows
            ],
        }

    async def read_summary_file(
        self,
        *,
        run_id: str | None = None,
        subject_path: str,
        file_summary_run_id: str | None,
    ) -> dict:
        """Return one summarized file entry by exact subject path."""
        payload = await self.list_summaries(
            run_id=run_id,
            file_summary_run_id=file_summary_run_id,
            limit=500,
            offset=0,
            language=None,
            parse_status=None,
            subject_path_prefix=subject_path,
        )
        items = payload["items"]
        for item in items:
            if item["subject_path"] == subject_path:
                return {
                    "run_id": payload["run_id"],
                    "file_summary_run_id": payload["file_summary_run_id"],
                    "item": item,
                }
        raise RepoKnowledgeMcpServiceError(f"Summary not found for subject_path={subject_path}")

    async def list_embedding_items(
        self,
        *,
        run_id: str,
        embedding_run_id: str | None,
        limit: int,
        offset: int,
        kind: str | None,
        language: str | None,
        subject_path_prefix: str | None,
    ) -> dict:
        """Return embedding metadata rows for a run using explicit or latest embedding run."""
        run = await self._get_scoped_run(run_id)
        embedding_run = await self._resolve_embedding_run(
            run=run,
            embedding_run_id=embedding_run_id,
        )
        if embedding_run is None:
            return {
                "run_id": run.id,
                "embedding_run_id": None,
                "limit": limit,
                "offset": offset,
                "items": [],
            }

        rows = await self.embedding_repo.list_for_embedding_run(
            embedding_run_id=embedding_run.id,
            source_run_id=run.id,
            kind=kind,
            language=language,
            subject_path_prefix=subject_path_prefix,
            limit=limit,
            offset=offset,
        )
        return {
            "run_id": run.id,
            "embedding_run_id": embedding_run.id,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "embedding_run_id": embedding.embedding_run_id,
                    "source_run_id": embedding.source_run_id,
                    "source_file_summary_run_id": embedding.source_file_summary_run_id,
                    "subject_id": subject.id,
                    "subject_path": subject.subject_path,
                    "language": subject.language,
                    "kind": embedding.kind,
                    "text_hash": embedding.text_hash,
                    "embedding_dims": embedding.embedding_dims,
                    "updated_at": embedding.updated_at.isoformat() if embedding.updated_at else None,
                }
                for embedding, subject, _snapshot in rows
            ],
        }

    async def list_repo_manager_segments(
        self,
        *,
        run_id: str | None = None,
        repo_manager_run_id: str | None,
        limit: int,
        offset: int,
        layer_hint: str | None,
        is_infrastructure: bool | None,
        group_key_prefix: str | None,
        include_members: bool,
    ) -> dict:
        """Return deterministic repo-manager segments for a run."""
        run = await self._get_scoped_run(run_id)
        summary_run = await self._resolve_repo_manager_run(
            run=run,
            repo_manager_run_id=repo_manager_run_id,
        )
        if summary_run is None:
            return {
                "run_id": run.id,
                "repo_manager_run_id": None,
                "limit": limit,
                "offset": offset,
                "include_members": include_members,
                "items": [],
            }

        rows = await self.summary_group_repo.list_groups_for_run(
            group_summary_run_id=summary_run.id,
            limit=limit,
            offset=offset,
            layer_hint=layer_hint,
            is_infrastructure=is_infrastructure,
            group_key_prefix=group_key_prefix,
        )
        member_map = {}
        if include_members:
            member_map = await self.summary_group_repo.list_members_for_groups(
                group_summary_run_id=summary_run.id,
                group_ids=[group.group_id for group, _summary in rows],
            )

        return {
            "run_id": run.id,
            "repo_manager_run_id": summary_run.id,
            "limit": limit,
            "offset": offset,
            "include_members": include_members,
            "items": [
                {
                    "group_id": group.group_id,
                    "group_key": group.group_key,
                    "group_label": group.group_label,
                    "layer_hint": group.layer_hint,
                    "member_count": group.member_count,
                    "dependency_neighbor_count": group.dependency_neighbor_count,
                    "is_infrastructure_seed": group.is_infrastructure_seed,
                    "name": summary.name if summary else None,
                    "overall_summary": summary.overall_summary if summary else None,
                    "business_purpose": summary.business_purpose if summary else None,
                    "responsibilities": list(summary.responsibilities or []) if summary else [],
                    "tags": list(summary.tags or []) if summary else [],
                    "representative_subject_ids": list(summary.representative_subject_ids or []) if summary else [],
                    "is_infrastructure": summary.is_infrastructure if summary else None,
                    "confidence": float(summary.confidence) if summary else None,
                    "updated_at": summary.updated_at.isoformat() if summary and summary.updated_at else None,
                    "members": [
                        {
                            "subject_id": subject.id,
                            "subject_path": subject.subject_path,
                            "language": subject.language,
                            "rank": member.rank,
                            "is_representative": member.is_representative,
                            "membership_reason": member.membership_reason,
                        }
                        for member, subject in member_map.get(group.group_id, [])
                    ],
                }
                for group, summary in rows
            ],
        }

    async def read_repo_manager_segment(
        self,
        *,
        run_id: str | None = None,
        group_id: str | None,
        group_key: str | None,
        repo_manager_run_id: str | None,
    ) -> dict:
        """Return one deterministic repo-manager segment by group_id or group_key."""
        if not group_id and not group_key:
            raise RepoKnowledgeMcpServiceError("Either group_id or group_key must be provided")
        run = await self._get_scoped_run(run_id)
        summary_run = await self._resolve_repo_manager_run(
            run=run,
            repo_manager_run_id=repo_manager_run_id,
        )
        if summary_run is None:
            raise RepoKnowledgeMcpServiceError("No completed repo-manager run found for run_id")

        row = await self.summary_group_repo.get_group_with_summary(
            group_summary_run_id=summary_run.id,
            group_id=group_id,
            group_key=group_key,
        )
        if row is None:
            raise RepoKnowledgeMcpServiceError("Group summary not found")
        group, summary = row

        member_map = await self.summary_group_repo.list_members_for_groups(
            group_summary_run_id=summary_run.id,
            group_ids=[group.group_id],
        )
        members = [
            {
                "subject_id": subject.id,
                "subject_path": subject.subject_path,
                "language": subject.language,
                "rank": member.rank,
                "is_representative": member.is_representative,
                "membership_reason": member.membership_reason,
            }
            for member, subject in member_map.get(group.group_id, [])
        ]
        return {
            "run_id": run.id,
            "repo_manager_run_id": summary_run.id,
            "item": {
                "group_id": group.group_id,
                "group_key": group.group_key,
                "group_label": group.group_label,
                "layer_hint": group.layer_hint,
                "member_count": group.member_count,
                "dependency_neighbor_count": group.dependency_neighbor_count,
                "is_infrastructure_seed": group.is_infrastructure_seed,
                "name": summary.name if summary else None,
                "overall_summary": summary.overall_summary if summary else None,
                "business_purpose": summary.business_purpose if summary else None,
                "responsibilities": list(summary.responsibilities or []) if summary else [],
                "tags": list(summary.tags or []) if summary else [],
                "representative_subject_ids": list(summary.representative_subject_ids or []) if summary else [],
                "is_infrastructure": summary.is_infrastructure if summary else None,
                "confidence": float(summary.confidence) if summary else None,
                "updated_at": summary.updated_at.isoformat() if summary and summary.updated_at else None,
                "members": members,
            },
        }

    async def get_repo_architecture(
        self,
        *,
        run_id: str | None = None,
        repo_manager_run_id: str | None,
    ) -> dict:
        """Return architecture overview and merged Mermaid diagram from a repo-manager run."""
        run = await self._get_scoped_run(run_id)
        summary_run = await self._resolve_repo_manager_run(
            run=run,
            repo_manager_run_id=repo_manager_run_id,
        )
        if summary_run is None:
            raise RepoKnowledgeMcpServiceError("No completed repo-manager run found for run_id")
        if not summary_run.architecture_overview and not summary_run.merged_mermaid_diagram:
            raise RepoKnowledgeMcpServiceError(
                "Repo-manager run has no architecture artifact yet — the merge phase may not have completed"
            )
        return {
            "run_id": run.id,
            "repo_manager_run_id": summary_run.id,
            "architecture_overview": summary_run.architecture_overview,
            "merged_mermaid_diagram": summary_run.merged_mermaid_diagram,
            "finished_at": summary_run.finished_at.isoformat() if summary_run.finished_at else None,
        }

    async def get_repo_full_summary(
        self,
        *,
        run_id: str | None = None,
        repo_full_summary_run_id: str | None,
    ) -> dict:
        """Return the README markdown from a repo full-summary run."""
        run = await self._get_scoped_run(run_id)

        if repo_full_summary_run_id:
            full_summary_run = await self.full_summary_run_repo.get_scoped(
                repo_full_summary_run_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            if full_summary_run is None:
                raise RepoKnowledgeMcpServiceError("Repo full-summary run not found")
            if full_summary_run.source_run_id != run.id:
                raise RepoKnowledgeMcpServiceError("Repo full-summary run does not belong to run_id")
        else:
            full_summary_run = await self.full_summary_run_repo.latest_completed_for_source(
                source_run_id=run.id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
        if full_summary_run is None:
            raise RepoKnowledgeMcpServiceError("No completed repo full-summary run found for run_id")

        artifact = await self.full_summary_repo.get_for_run(
            repo_full_summary_run_id=full_summary_run.id,
        )
        if artifact is None:
            raise RepoKnowledgeMcpServiceError("Repo full-summary artifact not found")
        return {
            "run_id": run.id,
            "repo_full_summary_run_id": full_summary_run.id,
            "readme_markdown": artifact.readme_markdown,
            "finished_at": full_summary_run.finished_at.isoformat() if full_summary_run.finished_at else None,
        }

    async def get_repo_structure(
        self,
        *,
        run_id: str | None = None,
        max_depth: int,
        include_file_counts: bool,
    ) -> dict:
        """Return deterministic repo tree from file snapshot paths."""
        run = await self._get_scoped_run(run_id)
        rows = await self.snapshot_repo.list_for_run_all(run_id=run.id)
        root = _new_dir_node(name="/", path="")
        for _snapshot, subject in rows:
            path = subject.subject_path.replace("\\\\", "/").strip("/")
            if not path:
                continue
            _insert_path(root=root, path=path)

        tree = _render_tree(node=root, depth=0, max_depth=max(1, max_depth), include_file_counts=include_file_counts)
        return {
            "run_id": run.id,
            "max_depth": max(1, max_depth),
            "include_file_counts": include_file_counts,
            "tree": tree,
        }

    async def get_file_content(
        self,
        *,
        run_id: str | None,
        subject_path: str,
        start_line: int,
        end_line: int | None,
        max_lines: int,
    ) -> dict:
        """Return a bounded line range from a file by its path."""
        run = await self._get_scoped_run(run_id)
        subject = await self.subject_repo.find_file_by_path(
            repo_address=run.repo_address, subject_path=subject_path
        )
        if subject is None:
            raise RepoKnowledgeMcpServiceError(f"File not found: {subject_path}")
        chunks = await self.chunk_repo.list_for_subject(run_id=run.id, subject_id=subject.id)
        if not chunks:
            raise RepoKnowledgeMcpServiceError(f"No stored content for: {subject_path}")
        content = "".join(c.content for c in chunks)
        lines = content.splitlines()
        total_lines = len(lines)

        if total_lines == 0:
            return {
                "path": subject_path,
                "start_line": 1,
                "end_line": 0,
                "total_lines": 0,
                "max_lines": max_lines,
                "truncated": False,
                "content": "",
            }

        start = max(1, start_line)
        if start > total_lines:
            raise RepoKnowledgeMcpServiceError(
                f"start_line {start} is beyond end of file ({total_lines} lines)"
            )

        if end_line is not None and end_line < start:
            raise RepoKnowledgeMcpServiceError("end_line must be greater than or equal to start_line")

        requested_end = total_lines if end_line is None else max(1, end_line)
        bounded_end = min(total_lines, requested_end, start + max_lines - 1)

        excerpt = "\n".join(lines[start - 1:bounded_end])
        truncated = start > 1 or bounded_end < total_lines

        payload = {
            "path": subject_path,
            "start_line": start,
            "end_line": bounded_end,
            "total_lines": total_lines,
            "max_lines": max_lines,
            "truncated": truncated,
            "content": excerpt,
        }
        if bounded_end < total_lines:
            payload["next_start_line"] = bounded_end + 1
        if start > 1:
            payload["previous_start_line"] = max(1, start - max_lines)
        return payload

    async def grep_code(
        self,
        *,
        run_id: str | None,
        pattern: str,
        path_prefix: str | None,
        ignore_case: bool,
        context_lines: int,
        max_matches: int,
        max_files: int,
        max_line_length: int,
    ) -> dict:
        """Search raw file content for a regex pattern, returning matching lines with context."""
        run = await self._get_scoped_run(run_id)

        flags = re.IGNORECASE if ignore_case else 0
        try:
            compiled = re.compile(pattern, flags)
        except re.error as exc:
            raise RepoKnowledgeMcpServiceError(f"Invalid regex: {exc}") from exc

        # Build query: join chunks → subjects, filter by run + file type
        stmt = (
            select(RepoSubjectRecord, RepoFileChunkRecord)
            .join(RepoFileChunkRecord, RepoFileChunkRecord.subject_id == RepoSubjectRecord.id)
            .where(
                RepoFileChunkRecord.run_id == run.id,
                RepoSubjectRecord.subject_type == "file",
            )
            .order_by(RepoSubjectRecord.subject_path, RepoFileChunkRecord.chunk_index)
        )
        if path_prefix:
            stmt = stmt.where(RepoSubjectRecord.subject_path.like(f"{path_prefix}%"))
        # DB-level pre-filter for literal patterns (no regex metacharacters)
        if not re.search(r'[\\^$\[\](){}*+?|]', pattern):
            stmt = stmt.where(RepoFileChunkRecord.content.ilike(f"%{pattern}%"))

        result = await self.session.execute(stmt)
        rows = result.all()

        # Group ordered chunks by file path
        file_chunks: dict[str, list[RepoFileChunkRecord]] = defaultdict(list)
        for subject, chunk in rows:
            file_chunks[subject.subject_path].append(chunk)

        matches = []
        total_matches = 0
        truncated = False

        for path in sorted(file_chunks.keys()):
            if len(matches) >= max_files:
                truncated = True
                break

            if total_matches >= max_matches:
                truncated = True
                break

            content = "".join(c.content for c in file_chunks[path])
            lines = content.splitlines()
            file_matches = []
            file_match_count = 0
            for i, line in enumerate(lines):
                if compiled.search(line):
                    ctx_start = max(0, i - context_lines)
                    ctx_end = min(len(lines), i + context_lines + 1)
                    file_match_count += 1
                    snippet_start = ctx_start + 1
                    snippet_end = ctx_end

                    if file_matches and snippet_start <= file_matches[-1]["end_line"]:
                        file_matches[-1]["end_line"] = max(file_matches[-1]["end_line"], snippet_end)
                        file_matches[-1]["match_lines"].append(i + 1)
                    else:
                        file_matches.append({
                            "start_line": snippet_start,
                            "end_line": snippet_end,
                            "match_lines": [i + 1],
                        })

                    total_matches += 1
                    if total_matches >= max_matches:
                        truncated = True
                        break
            if file_matches:
                matches.append({
                    "path": path,
                    "match_count": file_match_count,
                    "snippet_count": len(file_matches),
                    "matches": [
                        _render_grep_match_window(
                            start_line=snippet["start_line"],
                            end_line=snippet["end_line"],
                            match_lines=snippet["match_lines"],
                            lines=lines,
                            max_line_length=max_line_length,
                        )
                        for snippet in file_matches
                    ],
                })

            if total_matches >= max_matches:
                break

        return {
            "truncated": truncated,
            "max_matches": max_matches,
            "max_files": max_files,
            "max_line_length": max_line_length,
            "returned_match_count": total_matches,
            "returned_file_count": len(matches),
            "matches": matches,
        }

    async def glob_files(self, *, run_id: str | None, pattern: str, limit: int, offset: int) -> dict:
        """List indexed files whose paths match a glob pattern (e.g. 'src/**/*.ts')."""
        run = await self._get_scoped_run(run_id)
        rows = await self.snapshot_repo.list_for_run_all(run_id=run.id)
        matched = sorted(
            subject.subject_path
            for snapshot, subject in rows
            if subject.subject_type == "file" and fnmatch.fnmatch(subject.subject_path, pattern)
        )
        window = matched[offset: offset + limit]
        return {
            "pattern": pattern,
            "limit": limit,
            "offset": offset,
            "total": len(matched),
            "truncated": offset + len(window) < len(matched),
            "files": window,
        }

    async def _get_scoped_run(self, run_id: str | None) -> RepoRunRecord:
        if run_id is None:
            run = await self.run_repo.latest_completed_scoped(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            if run is None:
                raise RepoKnowledgeMcpServiceError("No completed ingestion run found")
            return run
        run = await self.run_repo.get_scoped(
            run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if run is None:
            raise RepoKnowledgeMcpServiceError("Run not found")
        return run

    async def _resolve_file_summary_run(
        self,
        *,
        run: RepoRunRecord,
        file_summary_run_id: str | None,
    ) -> RepoFileSummaryRunRecord | None:
        if file_summary_run_id:
            file_summary_run = await self.file_summary_run_repo.get_scoped(
                file_summary_run_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            if file_summary_run is None:
                raise RepoKnowledgeMcpServiceError("Extraction run not found")
            if file_summary_run.source_run_id != run.id:
                raise RepoKnowledgeMcpServiceError("Extraction run does not belong to run_id")
            return file_summary_run
        return await self.file_summary_run_repo.latest_completed_for_source(
            source_run_id=run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

    async def _resolve_embedding_run(
        self,
        *,
        run: RepoRunRecord,
        embedding_run_id: str | None,
    ) -> RepoEmbeddingRunRecord | None:
        if embedding_run_id:
            embedding_run = await self.embedding_run_repo.get_scoped(
                embedding_run_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            if embedding_run is None:
                raise RepoKnowledgeMcpServiceError("Embedding run not found")
            if embedding_run.source_run_id != run.id:
                raise RepoKnowledgeMcpServiceError("Embedding run does not belong to run_id")
            return embedding_run
        return await self.embedding_run_repo.latest_completed_for_source(
            source_run_id=run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

    async def _resolve_repo_manager_run(
        self,
        *,
        run: RepoRunRecord,
        repo_manager_run_id: str | None,
    ) -> RepoGroupSummaryRunRecord | None:
        if repo_manager_run_id:
            summary_run = await self.group_summary_run_repo.get_scoped(
                repo_manager_run_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )
            if summary_run is None:
                raise RepoKnowledgeMcpServiceError("Repo-manager run not found")
            if summary_run.source_run_id != run.id:
                raise RepoKnowledgeMcpServiceError("Repo-manager run does not belong to run_id")
            return summary_run
        return await self.group_summary_run_repo.latest_completed_for_source(
            source_run_id=run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

    @staticmethod
    def _serialize_run(run: RepoRunRecord) -> dict:
        return {
            "run_id": run.id,
            "status": run.status,
            "source_type": run.source_type,
            "repo_address": run.repo_address,
            "source_locator": run.source_locator,
            "files_seen": run.files_seen,
            "files_ingested": run.files_ingested,
            "files_skipped": run.files_skipped,
            "chunks_written": run.chunks_written,
            "parse_success_count": run.parse_success_count,
            "parse_failed_count": run.parse_failed_count,
            "edge_count_file": run.edge_count_file,
            "edge_count_symbol": run.edge_count_symbol,
            "error_message": run.error_message,
            "queued_at": run.queued_at.isoformat() if run.queued_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        }

    @staticmethod
    def _serialize_file_summary_run(run: RepoFileSummaryRunRecord | None) -> dict | None:
        if run is None:
            return None
        return {
            "file_summary_run_id": run.id,
            "source_run_id": run.source_run_id,
            "status": run.status,
            "prompt_version": run.prompt_version,
            "files_seen": run.files_seen,
            "files_summarized": run.files_summarized,
            "files_failed": run.files_failed,
            "error_message": run.error_message,
            "queued_at": run.queued_at.isoformat() if run.queued_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        }

    @staticmethod
    def _serialize_embedding_run(run: RepoEmbeddingRunRecord | None) -> dict | None:
        if run is None:
            return None
        return {
            "embedding_run_id": run.id,
            "source_run_id": run.source_run_id,
            "source_file_summary_run_id": run.source_file_summary_run_id,
            "status": run.status,
            "subjects_seen": run.subjects_seen,
            "subjects_embedded": run.subjects_embedded,
            "subjects_failed": run.subjects_failed,
            "error_message": run.error_message,
            "queued_at": run.queued_at.isoformat() if run.queued_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        }

    @staticmethod
    def _serialize_repo_manager_run(run: RepoGroupSummaryRunRecord | None) -> dict | None:
        if run is None:
            return None
        return {
            "repo_manager_run_id": run.id,
            "source_run_id": run.source_run_id,
            "source_file_summary_run_id": run.source_file_summary_run_id,
            "status": run.status,
            "prompt_version": run.prompt_version,
            "groups_seen": run.groups_seen,
            "groups_summarized": run.groups_summarized,
            "groups_failed": run.groups_failed,
            "members_seen": run.members_seen,
            "error_message": run.error_message,
            "queued_at": run.queued_at.isoformat() if run.queued_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        }

    async def list_group_summaries(
        self,
        *,
        run_id: str,
        group_summary_run_id: str | None,
        limit: int,
        offset: int,
        layer_hint: str | None,
        is_infrastructure: bool | None,
        group_key_prefix: str | None,
        include_members: bool,
    ) -> dict:
        return await self.list_repo_manager_segments(
            run_id=run_id,
            repo_manager_run_id=group_summary_run_id,
            limit=limit,
            offset=offset,
            layer_hint=layer_hint,
            is_infrastructure=is_infrastructure,
            group_key_prefix=group_key_prefix,
            include_members=include_members,
        )

    async def read_group_summary(
        self,
        *,
        run_id: str,
        group_id: str | None,
        group_key: str | None,
        group_summary_run_id: str | None,
    ) -> dict:
        return await self.read_repo_manager_segment(
            run_id=run_id,
            group_id=group_id,
            group_key=group_key,
            repo_manager_run_id=group_summary_run_id,
        )


def _new_dir_node(*, name: str, path: str) -> dict:
    return {
        "name": name,
        "type": "dir",
        "path": path,
        "children": {},
        "file_count": 0,
    }


def _insert_path(*, root: dict, path: str) -> None:
    parts = [part for part in path.split("/") if part]
    if not parts:
        return
    node = root
    current_path = []
    for idx, part in enumerate(parts):
        current_path.append(part)
        is_file = idx == len(parts) - 1
        children = node["children"]
        if part not in children:
            if is_file:
                children[part] = {
                    "name": part,
                    "type": "file",
                    "path": "/".join(current_path),
                }
            else:
                children[part] = _new_dir_node(name=part, path="/".join(current_path))
        if is_file:
            break
        node = children[part]


def _count_files(node: dict) -> int:
    if node["type"] == "file":
        return 1
    total = 0
    for child in node["children"].values():
        total += _count_files(child)
    node["file_count"] = total
    return total


def _render_tree(*, node: dict, depth: int, max_depth: int, include_file_counts: bool) -> dict:
    if node["type"] == "file":
        return {
            "name": node["name"],
            "type": "file",
            "path": node["path"],
        }

    if include_file_counts:
        _count_files(node)

    payload = {
        "name": node["name"],
        "type": "dir",
        "path": node["path"],
    }
    if include_file_counts:
        payload["file_count"] = node["file_count"]

    if depth >= max_depth:
        payload["truncated"] = bool(node["children"])
        return payload

    dirs: list[dict] = []
    files: list[dict] = []
    for child in node["children"].values():
        rendered = _render_tree(
            node=child,
            depth=depth + 1,
            max_depth=max_depth,
            include_file_counts=include_file_counts,
        )
        if rendered["type"] == "dir":
            dirs.append(rendered)
        else:
            files.append(rendered)
    dirs.sort(key=lambda item: item["name"])
    files.sort(key=lambda item: item["name"])
    payload["children"] = dirs + files
    return payload


def _truncate_line(text: str, max_line_length: int) -> str:
    if max_line_length <= 3 or len(text) <= max_line_length:
        return text
    return text[: max_line_length - 3] + "..."


def _render_grep_match_window(
    *,
    start_line: int,
    end_line: int,
    match_lines: list[int],
    lines: list[str],
    max_line_length: int,
) -> dict:
    match_line_set = set(match_lines)
    context = []
    for line_number in range(start_line, end_line + 1):
        context.append(
            {
                "line": line_number,
                "text": _truncate_line(lines[line_number - 1], max_line_length),
                "match": line_number in match_line_set,
            }
        )

    return {
        "start_line": start_line,
        "end_line": end_line,
        "match_lines": sorted(match_line_set),
        "context": context,
    }
