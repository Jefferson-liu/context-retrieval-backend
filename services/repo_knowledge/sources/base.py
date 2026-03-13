from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol


@dataclass(slots=True)
class SourceContext:
    """Resolved source context returned by source adapters."""

    source_type: str
    source_locator: str
    root_path: Path


@dataclass(slots=True)
class DiscoveredFile:
    """Metadata for one discovered source file."""

    absolute_path: Path
    relative_path: str


class RepoSourceAdapter(Protocol):
    """Interface for repository source adapters."""

    async def prepare(self) -> SourceContext:
        """Prepare the source and return a usable root path."""

    def iter_files(self) -> Iterable[DiscoveredFile]:
        """Iterate discovered files from the prepared source."""

    async def cleanup(self) -> None:
        """Cleanup any temporary resources after ingestion completes."""
