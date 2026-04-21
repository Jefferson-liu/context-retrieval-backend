from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("sse_starlette").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

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
    port=int(os.getenv("MCP_PORT", "8001")),
    instructions=(
        "Read-only MCP server exposing knowledge about a codebase. "
        "Use these tools to orient yourself in an unfamiliar repo: start with overview or architecture, "
        "then explore modules and individual files as needed."
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
        "Get a README-style summary of the entire codebase — what it does, its tech stack, "
        "and key concepts. Best starting point when exploring an unfamiliar repo."
    )
)
async def overview(
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
        return _log_result("overview", await service.get_repo_full_summary(repo_full_summary_run_id=None))


@mcp.tool(
    description=(
        "Get the high-level architecture of the codebase: a written overview of major components "
        "and a Mermaid diagram showing how they relate. Use this to understand system structure "
        "before reading individual files."
    )
)
async def architecture(
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
        return _log_result("architecture", await service.get_repo_architecture(repo_manager_run_id=None))


@mcp.tool(
    description=(
        "Get the repository directory and file tree. Use this to orient yourself in the codebase, "
        "discover where specific types of files live, or find a path before calling get_file_summary."
    )
)
async def file_tree(
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
        return _log_result("file_tree", await service.get_repo_structure(
            max_depth=max(1, min(max_depth, 20)),
            include_file_counts=include_file_counts,
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
        return _log_result("list_modules", await service.list_repo_manager_segments(
            repo_manager_run_id=None,
            limit=max(1, min(limit, 1000)),
            offset=max(0, offset),
            layer_hint=layer_hint,
            is_infrastructure=is_infrastructure,
            group_key_prefix=group_key_prefix,
            include_members=include_members,
        ))


@mcp.tool(
    description=(
        "Get detailed information about a specific architectural module — its purpose, "
        "responsibilities, tags, and the files that belong to it. "
        "Provide either group_id or group_key (from list_modules)."
    )
)
async def get_module(
    group_id: str | None = None,
    group_key: str | None = None,
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
        return _log_result("get_module", await service.read_repo_manager_segment(
            group_id=group_id,
            group_key=group_key,
            repo_manager_run_id=None,
        ))


@mcp.tool(
    description=(
        "Search summaries of source files. Filter by subject_path_prefix to scope "
        "to a directory (e.g. 'src/services/'), or by language (e.g. 'python', 'typescript'). "
        "Returns file paths, summaries, cluster tags, and relationships."
    )
)
async def search_file_summaries(
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
        return _log_result("search_file_summaries", await service.list_summaries(
            file_summary_run_id=None,
            limit=max(1, min(limit, 1000)),
            offset=max(0, offset),
            language=language,
            parse_status=parse_status,
            subject_path_prefix=subject_path_prefix,
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
        return _log_result("get_file_summary", await service.read_summary_file(
            subject_path=subject_path,
            file_summary_run_id=None,
        ))


def main() -> None:
    transport = os.getenv("REPO_KNOWLEDGE_MCP_TRANSPORT", "sse").strip().lower()
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError("REPO_KNOWLEDGE_MCP_TRANSPORT must be one of: stdio,sse,streamable-http")
    mcp.run(transport=transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
