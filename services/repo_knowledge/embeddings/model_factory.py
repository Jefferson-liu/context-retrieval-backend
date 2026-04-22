from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from config.settings import Settings

GEMINI_EMBED_PROVIDER = "gemini"
GEMINI_EMBED_MODEL = "gemini-embedding-001"

logger = logging.getLogger(__name__)


class RepoEmbeddingModelFactoryError(Exception):
    """Raised when embedding model selection or credentials are invalid."""


@dataclass(slots=True)
class RepoEmbeddingModel:
    """Async wrapper around a LangChain embedding model instance."""

    google_api_key: str
    model_names: tuple[str, ...]
    output_dimensionality: int
    timeout_seconds: int
    _model: object | None = None
    _active_model_idx: int = 0

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._embed_documents_with_fallback(texts)

    async def embed_query(self, query: str) -> list[float]:
        return await self._embed_query_with_fallback(query)

    async def _embed_documents_with_fallback(self, texts: list[str]) -> list[list[float]]:
        last_error: Exception | None = None
        for idx in range(self._active_model_idx, len(self.model_names)):
            model_name = self.model_names[idx]
            self._set_active_model(idx)
            try:
                return await self._embed_documents_once(texts)
            except Exception as exc:  # pragma: no cover - runtime provider failures
                last_error = exc
                if not _is_missing_model_error(exc):
                    raise
                logger.warning(
                    "Repo embedding model unavailable, trying fallback model model=%s error=%s",
                    model_name,
                    exc,
                )
        if last_error is not None:
            raise last_error
        raise RepoEmbeddingModelFactoryError("No embedding model candidates are configured")

    async def _embed_query_with_fallback(self, query: str) -> list[float]:
        last_error: Exception | None = None
        for idx in range(self._active_model_idx, len(self.model_names)):
            model_name = self.model_names[idx]
            self._set_active_model(idx)
            try:
                return await self._embed_query_once(query)
            except Exception as exc:  # pragma: no cover - runtime provider failures
                last_error = exc
                if not _is_missing_model_error(exc):
                    raise
                logger.warning(
                    "Repo embedding query model unavailable, trying fallback model model=%s error=%s",
                    model_name,
                    exc,
                )
        if last_error is not None:
            raise last_error
        raise RepoEmbeddingModelFactoryError("No embedding model candidates are configured")

    def _set_active_model(self, idx: int) -> None:
        if self._model is not None and self._active_model_idx == idx:
            return
        self._active_model_idx = idx
        self._model = _create_google_embedding_model(
            google_api_key=self.google_api_key,
            model_name=self.model_names[idx],
        )

    async def _embed_documents_once(self, texts: list[str]) -> list[list[float]]:
        model = self._model
        if model is None:
            raise RepoEmbeddingModelFactoryError("Embedding model was not initialized")
        if hasattr(model, "aembed_documents"):
            try:
                return await asyncio.wait_for(
                    model.aembed_documents(  # type: ignore[attr-defined]
                        texts,
                        task_type="retrieval_document",
                        output_dimensionality=self.output_dimensionality,
                    ),
                    timeout=self.timeout_seconds,
                )
            except TypeError:
                return await asyncio.wait_for(model.aembed_documents(texts), timeout=self.timeout_seconds)  # type: ignore[attr-defined]
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: model.embed_documents(  # type: ignore[attr-defined]
                        texts,
                        task_type="retrieval_document",
                        output_dimensionality=self.output_dimensionality,
                    ),
                ),
                timeout=self.timeout_seconds,
            )
        except TypeError:
            return await asyncio.wait_for(
                loop.run_in_executor(None, lambda: model.embed_documents(texts)),  # type: ignore[attr-defined]
                timeout=self.timeout_seconds,
            )

    async def _embed_query_once(self, query: str) -> list[float]:
        model = self._model
        if model is None:
            raise RepoEmbeddingModelFactoryError("Embedding model was not initialized")
        if hasattr(model, "aembed_query"):
            try:
                return await asyncio.wait_for(
                    model.aembed_query(  # type: ignore[attr-defined]
                        query,
                        task_type="retrieval_query",
                        output_dimensionality=self.output_dimensionality,
                    ),
                    timeout=self.timeout_seconds,
                )
            except TypeError:
                return await asyncio.wait_for(model.aembed_query(query), timeout=self.timeout_seconds)  # type: ignore[attr-defined]
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: model.embed_query(  # type: ignore[attr-defined]
                        query,
                        task_type="retrieval_query",
                        output_dimensionality=self.output_dimensionality,
                    ),
                ),
                timeout=self.timeout_seconds,
            )
        except TypeError:
            return await asyncio.wait_for(
                loop.run_in_executor(None, lambda: model.embed_query(query)),  # type: ignore[attr-defined]
                timeout=self.timeout_seconds,
            )


def create_repo_embedding_model(*, settings: Settings) -> RepoEmbeddingModel:
    """Build the hard-set Gemini embedding model for repo knowledge vectors."""
    provider = (settings.REPO_EMBED_MODEL_PROVIDER or GEMINI_EMBED_PROVIDER).strip().lower()
    requested_model = (settings.REPO_EMBED_MODEL_NAME or GEMINI_EMBED_MODEL).strip()

    if provider != GEMINI_EMBED_PROVIDER:
        raise RepoEmbeddingModelFactoryError(
            f"Unsupported repo embedding provider: {provider}. Expected {GEMINI_EMBED_PROVIDER}."
        )
    if not settings.GEMINI_API_KEY:
        raise RepoEmbeddingModelFactoryError("GEMINI_API_KEY is not configured")

    model_names = _build_model_candidates(requested_model)
    logger.info(
        "Repo embedding model candidates configured requested=%s candidates=%s",
        requested_model,
        list(model_names),
    )
    return RepoEmbeddingModel(
        google_api_key=settings.GEMINI_API_KEY,
        model_names=model_names,
        output_dimensionality=max(1, settings.REPO_EMBED_VECTOR_DIM),
        timeout_seconds=max(5, settings.REPO_EMBED_TIMEOUT_SECONDS),
    )


def _create_google_embedding_model(*, google_api_key: str, model_name: str) -> object:
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RepoEmbeddingModelFactoryError(
            "langchain-google-genai is required for repo embeddings"
        ) from exc
    return GoogleGenerativeAIEmbeddings(
        google_api_key=google_api_key,
        model=model_name,
    )


def _build_model_candidates(requested_model: str) -> tuple[str, ...]:
    requested = requested_model.strip()
    if not requested:
        requested = GEMINI_EMBED_MODEL

    # `text-embedding-004` is often unavailable on Gemini API keys; prefer Gemini-native embeddings.
    if requested in {"text-embedding-004", "models/text-embedding-004"}:
        requested = GEMINI_EMBED_MODEL

    ordered: list[str] = []

    def _add(value: str) -> None:
        candidate = value.strip()
        if candidate and candidate not in ordered:
            ordered.append(candidate)

    _add(requested)
    if requested.startswith("models/"):
        _add(requested.removeprefix("models/"))
    else:
        _add(f"models/{requested}")

    # Gemini embedding aliases across SDK/API versions.
    for alias in (
        "gemini-embedding-001",
        "models/gemini-embedding-001",
        "embedding-001",
        "models/embedding-001",
    ):
        _add(alias)

    return tuple(ordered)


def _is_missing_model_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "404" in message and "model" in message and "not found" in message
