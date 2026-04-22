from __future__ import annotations

import logging
import os
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

from services.repo_knowledge.sources.base import DiscoveredFile

logger = logging.getLogger(__name__)


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".venv-wsl",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
}


def iter_repo_files(
    *,
    root_path: Path,
    include_extensions: set[str],
    excluded_dirs: set[str],
    exclude_globs: list[str],
) -> Iterable[DiscoveredFile]:
    """Yield repository files that match extension and exclusion filters."""
    if not root_path.exists() or not root_path.is_dir():
        logger.warning("Discovery root is not a directory root=%s", root_path)
        return []

    merged_excluded_dirs = {d for d in DEFAULT_EXCLUDED_DIRS}
    merged_excluded_dirs.update({d.strip() for d in excluded_dirs if d.strip()})

    discovered: list[DiscoveredFile] = []

    def _on_walk_error(exc: OSError) -> None:
        logger.warning(
            "Discovery skipped inaccessible directory root=%s path=%s error=%s",
            root_path,
            getattr(exc, "filename", None),
            exc,
        )

    for current_root, dir_names, file_names in os.walk(
        root_path,
        topdown=True,
        onerror=_on_walk_error,
        followlinks=False,
    ):
        current_dir = Path(current_root)
        rel_dir = current_dir.relative_to(root_path)

        kept_dirs: list[str] = []
        for directory_name in dir_names:
            if directory_name in merged_excluded_dirs:
                continue
            next_rel = (rel_dir / directory_name).as_posix()
            if exclude_globs and any(fnmatch(next_rel, pattern) for pattern in exclude_globs if pattern):
                continue
            kept_dirs.append(directory_name)
        dir_names[:] = kept_dirs

        for file_name in file_names:
            file_path = current_dir / file_name
            rel = (rel_dir / file_name).as_posix()

            if exclude_globs and any(fnmatch(rel, pattern) for pattern in exclude_globs if pattern):
                continue

            suffix = file_path.suffix.lower()
            if include_extensions and suffix not in include_extensions:
                continue

            try:
                if not file_path.is_file():
                    continue
            except OSError as exc:
                logger.warning(
                    "Discovery skipped inaccessible path root=%s path=%s error=%s",
                    root_path,
                    file_path,
                    exc,
                )
                continue

            discovered.append(DiscoveredFile(absolute_path=file_path, relative_path=rel))

    logger.info(
        "Discovery completed root=%s files=%s include_ext_count=%s exclude_dir_count=%s exclude_glob_count=%s",
        root_path,
        len(discovered),
        len(include_extensions),
        len(merged_excluded_dirs),
        len(exclude_globs),
    )
    return discovered
