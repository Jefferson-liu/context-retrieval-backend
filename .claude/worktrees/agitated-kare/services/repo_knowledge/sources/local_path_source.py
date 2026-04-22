from __future__ import annotations

import logging
from pathlib import Path

from services.repo_knowledge.discovery_service import iter_repo_files
from services.repo_knowledge.sources.base import DiscoveredFile, RepoSourceAdapter, SourceContext

logger = logging.getLogger(__name__)


class LocalPathSourceAdapter(RepoSourceAdapter):
    """Reads repository content directly from a local filesystem path."""

    def __init__(
        self,
        *,
        source_path: str,
        include_extensions: set[str],
        excluded_dirs: set[str],
        exclude_globs: list[str],
    ) -> None:
        self._source_path = Path(source_path).expanduser()
        self._include_extensions = include_extensions
        self._excluded_dirs = excluded_dirs
        self._exclude_globs = exclude_globs
        self._root_path: Path | None = None

    async def prepare(self) -> SourceContext:
        root = self._source_path.resolve()
        self._root_path = root
        logger.info("LocalPathSource prepared root=%s", root)
        return SourceContext(source_type="local_path", source_locator=str(root), root_path=root)

    def iter_files(self):
        if self._root_path is None:
            logger.warning("LocalPathSource iter_files called before prepare")
            return []
        logger.info("LocalPathSource iterating files root=%s", self._root_path)
        return iter_repo_files(
            root_path=self._root_path,
            include_extensions=self._include_extensions,
            excluded_dirs=self._excluded_dirs,
            exclude_globs=self._exclude_globs,
        )

    async def cleanup(self) -> None:
        logger.debug("LocalPathSource cleanup complete")
        return None
