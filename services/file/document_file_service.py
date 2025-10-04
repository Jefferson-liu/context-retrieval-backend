import asyncio
import logging
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


class DocumentFileService:
    """Handles persistence of uploaded documents to the git working tree."""

    def __init__(self, repo_path: Optional[str] = settings.GIT_REPO_PATH) -> None:
        self._base_path = Path(repo_path).resolve() if repo_path else None
        if not self._base_path:
            logger.warning("GIT_REPO_PATH is not configured; document files will not be written to disk.")
            self._documents_dir: Optional[Path] = None
            return

        self._documents_dir = self._base_path / "documents"
        self._documents_dir.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self._documents_dir is not None

    async def write_document(self, document_id: int, doc_name: str, context: str) -> Optional[Path]:
        if not self.enabled:
            return None

        path = self._build_document_path(document_id, doc_name)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._write_file, path, context)
        return path

    async def delete_document(self, document_id: int, doc_name: str) -> Optional[Path]:
        if not self.enabled:
            return None

        path = self._build_document_path(document_id, doc_name)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._remove_file, path)
        return path

    def _write_file(self, path: Path, context: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(context)

    def _remove_file(self, path: Path) -> None:
        if path.exists():
            path.unlink()

    def _build_document_path(self, document_id: int, doc_name: str) -> Path:
        assert self._documents_dir is not None  # Guarded by enabled check
        safe_name = Path(doc_name).name or f"document_{document_id}.txt"
        return self._documents_dir / f"{document_id}_{safe_name}"
