from __future__ import annotations

import os
from pathlib import Path
import sys

# `mcp run scripts/foo.py` loads with scripts/ as import base.
# Ensure repo root is importable for config/infrastructure/services modules.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_settings
from infrastructure.database import SessionLocal
from mcp.server.fastmcp import FastMCP
from services.repo_knowledge.mcp_tools_service import (
    RepoKnowledgeMcpService,
    RepoKnowledgeMcpServiceError,
)

mcp = FastMCP(
    name="repo-knowledge-mcp",
    instructions=(
        "Read-only MCP server for repository knowledge artifacts. "
        "Provides scoped inspection tools for runs, files, edges, summaries, group summaries, embeddings, and repo structure."
    ),
)


def _resolve_scope(tenant_id: str | None, user_id: str | None) -> tuple[str, str]:
    settings = get_settings()
    resolved_tenant = (tenant_id or "").strip()
    resolved_user = (user_id or "").strip()

    if settings.USE_PLACEHOLDER_SCOPE:
        resolved_tenant = resolved_tenant or settings.DEFAULT_TENANT_ID
        resolved_user = resolved_user or settings.DEFAULT_USER_ID

    if not resolved_tenant or not resolved_user:
        raise RepoKnowledgeMcpServiceError(
            "Missing scope. Provide tenant_id and user_id (or enable placeholder scope defaults)."
        )
    return resolved_tenant, resolved_user


@mcp.tool(description="Get one ingestion run overview plus latest file_summary/embedding run metadata.")
async def repo_run_overview(
    run_id: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(
            session,
            tenant_id=resolved_tenant,
            user_id=resolved_user,
        )
        return await service.get_run_overview(run_id=run_id)


@mcp.tool(description="List run file snapshots (repo_file_snapshots joined with repo_subjects).")
async def repo_list_files(
    run_id: str,
    limit: int = 100,
    offset: int = 0,
    ingest_status: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(
            session,
            tenant_id=resolved_tenant,
            user_id=resolved_user,
        )
        return await service.list_files(
            run_id=run_id,
            limit=max(1, min(limit, 1000)),
            offset=max(0, offset),
            ingest_status=ingest_status,
        )


@mcp.tool(description="List run dependency edges (repo_edges joined with from/to subjects).")
async def repo_list_edges(
    run_id: str,
    limit: int = 100,
    offset: int = 0,
    edge_type: str | None = None,
    from_subject_type: str | None = None,
    to_subject_type: str | None = None,
    language: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(
            session,
            tenant_id=resolved_tenant,
            user_id=resolved_user,
        )
        return await service.list_edges(
            run_id=run_id,
            limit=max(1, min(limit, 1000)),
            offset=max(0, offset),
            edge_type=edge_type,
            from_subject_type=from_subject_type,
            to_subject_type=to_subject_type,
            language=language,
        )


@mcp.tool(
    description=(
        "List summarized files for a source run. If file_summary_run_id is omitted, uses latest completed file_summary run."
    )
)
async def repo_list_summaries(
    run_id: str,
    file_summary_run_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    language: str | None = None,
    parse_status: str | None = None,
    subject_path_prefix: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(
            session,
            tenant_id=resolved_tenant,
            user_id=resolved_user,
        )
        return await service.list_summaries(
            run_id=run_id,
            file_summary_run_id=file_summary_run_id,
            limit=max(1, min(limit, 1000)),
            offset=max(0, offset),
            language=language,
            parse_status=parse_status,
            subject_path_prefix=subject_path_prefix,
        )


@mcp.tool(
    description=(
        "Read one summarized file by exact subject_path. "
        "If file_summary_run_id is omitted, uses latest completed file_summary run."
    )
)
async def repo_read_summary_file(
    run_id: str,
    subject_path: str,
    file_summary_run_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(
            session,
            tenant_id=resolved_tenant,
            user_id=resolved_user,
        )
        return await service.read_summary_file(
            run_id=run_id,
            subject_path=subject_path,
            file_summary_run_id=file_summary_run_id,
        )


@mcp.tool(
    description=(
        "List embedding rows for a source run. "
        "If embedding_run_id is omitted, uses latest completed embedding run."
    )
)
async def repo_list_embedding_items(
    run_id: str,
    embedding_run_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    kind: str | None = None,
    language: str | None = None,
    subject_path_prefix: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(
            session,
            tenant_id=resolved_tenant,
            user_id=resolved_user,
        )
        return await service.list_embedding_items(
            run_id=run_id,
            embedding_run_id=embedding_run_id,
            limit=max(1, min(limit, 1000)),
            offset=max(0, offset),
            kind=kind,
            language=language,
            subject_path_prefix=subject_path_prefix,
        )


@mcp.tool(
    description=(
        "List deterministic repo-manager segments for a source run. "
        "If repo_manager_run_id is omitted, uses the latest completed repo-manager run."
    )
)
async def repo_list_repo_manager_segments(
    run_id: str,
    repo_manager_run_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    layer_hint: str | None = None,
    is_infrastructure: bool | None = None,
    group_key_prefix: str | None = None,
    include_members: bool = False,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(
            session,
            tenant_id=resolved_tenant,
            user_id=resolved_user,
        )
        return await service.list_repo_manager_segments(
            run_id=run_id,
            repo_manager_run_id=repo_manager_run_id,
            limit=max(1, min(limit, 1000)),
            offset=max(0, offset),
            layer_hint=layer_hint,
            is_infrastructure=is_infrastructure,
            group_key_prefix=group_key_prefix,
            include_members=include_members,
        )


@mcp.tool(
    description=(
        "Read one deterministic repo-manager segment by group_id or group_key. "
        "If repo_manager_run_id is omitted, uses the latest completed repo-manager run."
    )
)
async def repo_read_repo_manager_segment(
    run_id: str,
    group_id: str | None = None,
    group_key: str | None = None,
    repo_manager_run_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(
            session,
            tenant_id=resolved_tenant,
            user_id=resolved_user,
        )
        return await service.read_repo_manager_segment(
            run_id=run_id,
            group_id=group_id,
            group_key=group_key,
            repo_manager_run_id=repo_manager_run_id,
        )


@mcp.tool(
    description="Return deterministic repository tree structure from run file snapshots."
)
async def repo_structure(
    run_id: str,
    max_depth: int = 4,
    include_file_counts: bool = True,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(
            session,
            tenant_id=resolved_tenant,
            user_id=resolved_user,
        )
        return await service.get_repo_structure(
            run_id=run_id,
            max_depth=max(1, min(max_depth, 20)),
            include_file_counts=include_file_counts,
        )


def main() -> None:
    transport = os.getenv("REPO_KNOWLEDGE_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError("REPO_KNOWLEDGE_MCP_TRANSPORT must be one of: stdio,sse,streamable-http")
    mcp.run(transport=transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
