from __future__ import annotations

import logging

from services.repo_knowledge.sources.base import RepoSourceAdapter, SourceContext

logger = logging.getLogger(__name__)


class GitCloneSourceAdapter(RepoSourceAdapter):
    """Stub adapter for future git-url ingestion."""

    def __init__(self, *, source_path: str) -> None:
        self.source_path = source_path

    async def prepare(self) -> SourceContext:
        logger.warning("GitCloneSourceAdapter prepare called but feature is not implemented source=%s", self.source_path)
        raise NotImplementedError("git_url source_type is not implemented yet")

    def iter_files(self):
        return []

    async def cleanup(self) -> None:
        return None
