from __future__ import annotations

import logging

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


LANGUAGE_BY_EXTENSION: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".jsx": Language.JS,
    ".ts": Language.TS,
    ".tsx": Language.TS,
}


class RepoChunkingService:
    """LangChain-based chunking service for repository files."""

    def __init__(self, *, chunk_size: int, chunk_overlap: int) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        logger.info("RepoChunkingService initialized chunk_size=%s chunk_overlap=%s", chunk_size, chunk_overlap)

    def chunk_text(self, *, text: str, extension: str) -> list[str]:
        """Split file text into chunks using language-aware separators when available."""
        if not text:
            logger.debug("Chunking skipped for empty text extension=%s", extension)
            return []

        language = LANGUAGE_BY_EXTENSION.get(extension.lower())
        if language:
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=language,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        else:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", " ", ""],
            )
        docs = splitter.create_documents([text])
        chunks = [doc.page_content for doc in docs if doc.page_content]
        logger.debug("Chunking completed extension=%s chunk_count=%s", extension, len(chunks))
        return chunks
