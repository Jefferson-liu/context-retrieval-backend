from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

import pygit2

from services.repo_knowledge.discovery_service import iter_repo_files
from services.repo_knowledge.sources.base import DiscoveredFile, RepoSourceAdapter, SourceContext

logger = logging.getLogger(__name__)


class GitCloneSourceAdapter(RepoSourceAdapter):
    """Clones a git repository to a temp directory for ingestion."""

    def __init__(
        self,
        *,
        source_path: str,
        include_extensions: set[str],
        excluded_dirs: set[str],
        exclude_globs: list[str],
        git_token: str | None = None,
    ) -> None:
        self._source_url = source_path
        self._include_extensions = include_extensions
        self._excluded_dirs = excluded_dirs
        self._exclude_globs = exclude_globs
        self._git_token = git_token
        self._root_path: Path | None = None

    async def prepare(self) -> SourceContext:
        tmp_dir = tempfile.mkdtemp(prefix="repo_ingest_")
        logger.info("GitCloneSource cloning url=%s into tmp=%s has_token=%s", self._source_url, tmp_dir, self._git_token is not None)
        callbacks = None
        if self._git_token:
            callbacks = pygit2.RemoteCallbacks(
                credentials=pygit2.UserPass("x-access-token", self._git_token)
            )
        try:
            pygit2.clone_repository(self._source_url, tmp_dir, callbacks=callbacks)
        except pygit2.GitError as exc:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            logger.error("GitCloneSource clone failed url=%s error=%s", self._source_url, exc)
            raise RuntimeError(f"Git clone failed for {self._source_url}: {exc}") from exc

        root = Path(tmp_dir).resolve()
        self._root_path = root
        logger.info("GitCloneSource prepared root=%s", root)
        return SourceContext(source_type="git_url", source_locator=self._source_url, root_path=root)

    def iter_files(self):
        if self._root_path is None:
            logger.warning("GitCloneSource iter_files called before prepare")
            return []
        logger.info("GitCloneSource iterating files root=%s", self._root_path)
        return iter_repo_files(
            root_path=self._root_path,
            include_extensions=self._include_extensions,
            excluded_dirs=self._excluded_dirs,
            exclude_globs=self._exclude_globs,
        )

    async def cleanup(self) -> None:
        if self._root_path is not None and self._root_path.exists():
            logger.info("GitCloneSource cleaning up tmp=%s", self._root_path)
            shutil.rmtree(self._root_path, ignore_errors=True)
        else:
            logger.debug("GitCloneSource cleanup skipped (no root path)")
