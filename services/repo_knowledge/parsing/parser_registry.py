from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Protocol

from services.repo_knowledge.parsing.tree_sitter_python import TreeSitterPythonParser
from services.repo_knowledge.parsing.tree_sitter_ts_js import TreeSitterTsJsParser
from services.repo_knowledge.parsing.types import ParsedFileGraph

logger = logging.getLogger(__name__)


class AstParser(Protocol):
    """AST parser contract used by the ingestion service."""

    def parse(self, *, file_path: str, source_text: str) -> ParsedFileGraph:
        """Parse source code and return graph artifacts."""


@dataclass(slots=True)
class ParserSelection:
    """Parser lookup output."""

    language: str
    parser: AstParser | None


class ParserRegistry:
    """Language-to-parser registry for repository ingestion."""

    def __init__(self, *, enabled_languages: set[str]) -> None:
        self._enabled_languages = {item.lower().strip() for item in enabled_languages if item.strip()}
        self._python_parser = TreeSitterPythonParser() if "python" in self._enabled_languages else None
        self._ts_js_parser = (
            TreeSitterTsJsParser(enabled_languages=self._enabled_languages)
            if {"typescript", "javascript"}.intersection(self._enabled_languages)
            else None
        )
        logger.info("Parser registry initialized enabled_languages=%s", sorted(self._enabled_languages))

    @staticmethod
    def detect_language(file_path: str) -> str | None:
        suffix = Path(file_path).suffix.lower()
        if suffix == ".py":
            return "python"
        if suffix in {".ts", ".tsx"}:
            return "typescript"
        if suffix in {".js", ".jsx", ".mjs", ".cjs"}:
            return "javascript"
        return None

    def get_parser(self, *, file_path: str) -> ParserSelection:
        language = self.detect_language(file_path)
        if language is None:
            logger.debug("Parser registry no language match file=%s", file_path)
            return ParserSelection(language="unknown", parser=None)
        if language == "python":
            logger.debug("Parser registry selected python parser file=%s available=%s", file_path, self._python_parser is not None)
            return ParserSelection(language=language, parser=self._python_parser)
        if language in {"typescript", "javascript"}:
            logger.debug("Parser registry selected ts/js parser file=%s available=%s", file_path, self._ts_js_parser is not None)
            return ParserSelection(language=language, parser=self._ts_js_parser)
        logger.debug("Parser registry language unsupported file=%s language=%s", file_path, language)
        return ParserSelection(language=language, parser=None)
