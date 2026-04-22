from __future__ import annotations

import json
import logging
import os

from mcp.server.fastmcp import FastMCP

from config.settings import get_settings
from infrastructure.database import SessionLocal
from services.repo_knowledge.mcp_tools_service import (
    RepoKnowledgeMcpService,
    RepoKnowledgeMcpServiceError,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="repo-knowledge-agent-mcp",
    instructions=(
        "Read-only MCP server exposing indexed codebase knowledge to autonomous agents. "
        "If multiple repos are indexed, call list_runs first to choose the right run_id, "
        "then use overview or architecture before drilling into files."
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


def _log_result(tool_name: str, result: dict) -> dict:
    logger.debug("tool=%s response=%s", tool_name, json.dumps(result, default=str))
    return result


@mcp.tool(
    description=(
        "List recent scoped ingestion runs so an agent can choose the correct indexed codebase before "
        "calling overview, architecture, or file tools. Defaults to completed runs only."
    )
)
async def list_runs(
    limit: int = 20,
    offset: int = 0,
    status: str | None = "completed",
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(session, tenant_id=resolved_tenant, user_id=resolved_user)
        return _log_result("list_runs", await service.list_runs(
            limit=max(1, min(limit, 100)),
            offset=max(0, offset),
            status=status or None,
        ))


@mcp.tool(
    description=(
        "Get a README-style summary of the entire codebase — what it does, its tech stack, "
        "and key concepts. Best starting point when exploring an unfamiliar repo."
    )
)
async def overview(
    run_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(session, tenant_id=resolved_tenant, user_id=resolved_user)
        return _log_result("overview", await service.get_repo_full_summary(run_id=run_id, repo_full_summary_run_id=None))


@mcp.tool(
    description=(
        "Get the high-level architecture of the codebase: a written overview of major components "
        "and a Mermaid diagram showing how they relate. Use this to understand system structure "
        "before reading individual files."
    )
)
async def architecture(
    run_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(session, tenant_id=resolved_tenant, user_id=resolved_user)
        return _log_result("architecture", await service.get_repo_architecture(run_id=run_id, repo_manager_run_id=None))


@mcp.tool(
    description=(
        "Get the repository directory and file tree. Use this to orient yourself in the codebase, "
        "discover where specific types of files live, or find a path before calling get_file_summary."
    )
)
async def file_tree(
    run_id: str | None = None,
    max_depth: int = 4,
    include_file_counts: bool = True,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(session, tenant_id=resolved_tenant, user_id=resolved_user)
        return _log_result("file_tree", await service.get_repo_structure(
            run_id=run_id, max_depth=max(1, min(max_depth, 20)), include_file_counts=include_file_counts,
        ))


@mcp.tool(
    description=(
        "List the architectural modules that make up this codebase, each with a name, purpose, "
        "layer, and summary. Use include_members=true to also return the files that belong to each "
        "module in the same call. Filter by layer_hint (e.g. 'service', 'infrastructure') or "
        "group_key_prefix to narrow results."
    )
)
async def list_modules(
    run_id: str | None = None,
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
        service = RepoKnowledgeMcpService(session, tenant_id=resolved_tenant, user_id=resolved_user)
        return _log_result("list_modules", await service.list_repo_manager_segments(
            run_id=run_id, repo_manager_run_id=None,
            limit=max(1, min(limit, 1000)), offset=max(0, offset),
            layer_hint=layer_hint, is_infrastructure=is_infrastructure,
            group_key_prefix=group_key_prefix, include_members=include_members,
        ))


@mcp.tool(
    description=(
        "Get detailed information about a specific architectural module — its purpose, "
        "responsibilities, tags, and the files that belong to it. "
        "Provide either group_id or group_key (from list_modules)."
    )
)
async def get_module(
    run_id: str | None = None,
    group_id: str | None = None,
    group_key: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(session, tenant_id=resolved_tenant, user_id=resolved_user)
        return _log_result("get_module", await service.read_repo_manager_segment(
            run_id=run_id, group_id=group_id, group_key=group_key, repo_manager_run_id=None,
        ))


@mcp.tool(
    description=(
        "Search summaries of source files. Filter by subject_path_prefix to scope "
        "to a directory (e.g. 'src/services/'), or by language (e.g. 'python', 'typescript'). "
        "Returns file paths, summaries, cluster tags, and relationships."
    )
)
async def search_file_summaries(
    run_id: str | None = None,
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
        service = RepoKnowledgeMcpService(session, tenant_id=resolved_tenant, user_id=resolved_user)
        return _log_result("search_file_summaries", await service.list_summaries(
            run_id=run_id, file_summary_run_id=None,
            limit=max(1, min(limit, 1000)), offset=max(0, offset),
            language=language, parse_status=parse_status, subject_path_prefix=subject_path_prefix,
        ))


@mcp.tool(
    description=(
        "Get the summary for a specific source file by its exact path — "
        "what the file does, its key relationships, cluster membership, and role in the codebase. "
        "Use file_tree or search_file_summaries first if you need to discover the path."
    )
)
async def get_file_summary(
    subject_path: str,
    run_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(session, tenant_id=resolved_tenant, user_id=resolved_user)
        return _log_result("get_file_summary", await service.read_summary_file(
            run_id=run_id, subject_path=subject_path, file_summary_run_id=None,
        ))


@mcp.tool(
    description=(
        "Read a bounded line range from a file by its exact path. "
        "Use start_line/end_line to zoom in. By default, returns the first 120 lines "
        "and includes pagination metadata when truncated."
    )
)
async def get_file(
    subject_path: str,
    run_id: str | None = None,
    start_line: int = 1,
    end_line: int | None = None,
    max_lines: int = 120,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(session, tenant_id=resolved_tenant, user_id=resolved_user)
        return _log_result("get_file", await service.get_file_content(
            run_id=run_id,
            subject_path=subject_path,
            start_line=max(1, start_line),
            end_line=None if end_line is None else max(1, end_line),
            max_lines=max(1, min(max_lines, 400)),
        ))


@mcp.tool(
    description=(
        "Search file contents with a regex pattern. Returns compact snippet windows "
        "around matches, grouped by file path. "
        "Use path_prefix to scope to a directory (e.g. 'src/services/'). "
        "ignore_case defaults to true. context_lines defaults to 1. "
        "Results are capped by both max_matches and max_files, and lines are truncated "
        "to max_line_length characters for token efficiency."
    )
)
async def grep_code(
    pattern: str,
    run_id: str | None = None,
    path_prefix: str | None = None,
    ignore_case: bool = True,
    context_lines: int = 1,
    max_matches: int = 12,
    max_files: int = 8,
    max_line_length: int = 180,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(session, tenant_id=resolved_tenant, user_id=resolved_user)
        return _log_result("grep_code", await service.grep_code(
            run_id=run_id,
            pattern=pattern,
            path_prefix=path_prefix,
            ignore_case=ignore_case,
            context_lines=max(0, min(context_lines, 5)),
            max_matches=max(1, min(max_matches, 100)),
            max_files=max(1, min(max_files, 50)),
            max_line_length=max(40, min(max_line_length, 600)),
        ))


@mcp.tool(
    description=(
        "Find indexed files whose paths match a glob pattern. "
        "Use '*' within a segment and chain segments with '/'. "
        "Examples: '*.py', 'src/*.ts', 'services/*/*.py'. "
        "Returns a paginated list of matching file paths."
    )
)
async def glob_files(
    pattern: str,
    run_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    resolved_tenant, resolved_user = _resolve_scope(tenant_id, user_id)
    async with SessionLocal() as session:
        service = RepoKnowledgeMcpService(session, tenant_id=resolved_tenant, user_id=resolved_user)
        return _log_result("glob_files", await service.glob_files(
            run_id=run_id,
            pattern=pattern,
            limit=max(1, min(limit, 500)),
            offset=max(0, offset),
        ))
