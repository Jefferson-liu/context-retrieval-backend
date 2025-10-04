import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Iterable, Optional

import pygit2

from config import settings

logger = logging.getLogger(__name__)


def _get_signature() -> pygit2.Signature:
    name = os.getenv("GIT_AUTHOR_NAME", "Context Retrieval Bot")
    email = os.getenv("GIT_AUTHOR_EMAIL", "context-bot@example.com")
    timestamp = int(time.time())
    if time.localtime().tm_isdst and time.daylight:
        offset = -time.altzone // 60
    else:
        offset = -time.timezone // 60
    return pygit2.Signature(name, email, timestamp, offset)


class GitService:
    """Thin wrapper around pygit2 for staging and committing document changes."""

    def __init__(self, repo_path: Optional[str] = settings.GIT_REPO_PATH) -> None:
        self._repo_path = Path(repo_path).resolve() if repo_path else None
        self._repo: Optional[pygit2.Repository] = None

        if not self._repo_path:
            logger.warning("GIT_REPO_PATH is not configured; git commits will be skipped.")
            return

        try:
            self._repo = pygit2.Repository(str(self._repo_path))
        except (pygit2.GitError, ValueError) as exc:
            logger.error("Failed to open git repository at %s: %s", self._repo_path, exc)
            self._repo = None

    @property
    def enabled(self) -> bool:
        return self._repo is not None

    async def commit_changes(
        self,
        message: str,
        added_paths: Optional[Iterable[Path]] = None,
        removed_paths: Optional[Iterable[Path]] = None,
    ) -> bool:
        """
        Stage added/updated and removed files, then create a commit.

        Args:
            message: Commit message supplied by the caller.
            added_paths: Iterable of absolute file paths to add/update.
            removed_paths: Iterable of absolute file paths to stage for deletion.

        Returns:
            True if a commit was created, False otherwise (e.g., no repo or no changes).
        """
        if not self.enabled:
            return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._commit_changes,
            message,
            tuple(added_paths or ()),
            tuple(removed_paths or ()),
        )

    def _commit_changes(
        self,
        message: str,
        added_paths: Iterable[Path],
        removed_paths: Iterable[Path],
    ) -> bool:
        assert self._repo is not None  # Guarded by enabled
        index = self._repo.index
        index.read()

        for path in removed_paths:
            try:
                rel_path = self._relativize(path)
                index.remove(rel_path)
            except KeyError:
                logger.debug("Skipping removal for %s; not tracked in index", path)

        for path in added_paths:
            rel_path = self._relativize(path)
            if not path.exists():
                logger.warning("Cannot add %s because it does not exist on disk", path)
                continue
            index.add(rel_path)

        index.write()
        tree_oid = index.write_tree()

        parents = []
        if not self._repo.head_is_unborn:
            head_commit = self._repo[self._repo.head.target]
            parents.append(head_commit.id)
            if head_commit.tree_id == tree_oid:
                logger.debug("No staged changes detected; skipping commit")
                return False

        author = _get_signature()
        self._repo.create_commit("HEAD", author, author, message, tree_oid, parents)
        logger.info("Created git commit: %s", message)
        return True

    def _relativize(self, path: Path) -> str:
        rel_path = path.resolve().relative_to(self._repo_path)
        # Git expects forward slashes
        return rel_path.as_posix()
