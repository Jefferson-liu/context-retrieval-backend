from __future__ import annotations

import logging
from typing import List
from infrastructure.context import ContextScope
from infrastructure.database.repositories.vector_search_repository import SearchRepository
from infrastructure.ai.embedding import Embedder
from sqlalchemy.ext.asyncio import AsyncSession
from schemas import VectorSearchResult
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from config import settings

logger = logging.getLogger(__name__)


class _RerankItem(BaseModel):
    chunk_id: int = Field(..., description="Chunk identifier from the candidate list.")
    relevance: float = Field(..., ge=0.0, le=1.0, description="Relevance score between 0 and 1.")


class _RerankResponse(BaseModel):
    results: List[_RerankItem] = Field(default_factory=list)


class SearchService:
    def __init__(
        self,
        db: AsyncSession,
        context: ContextScope,
        embedder: Embedder,
        *,
        rerank_llm: BaseChatModel | None = None,
    ):
        self.db = db
        self.context = context
        self.search_repo = SearchRepository(db, context)
        self.embedder = embedder
        self.rerank_llm = rerank_llm
        self._rerank_chain = self._build_rerank_chain() if self.rerank_llm else None

    async def semantic_search(self, query_text: str, top_k: int = 5) -> list[VectorSearchResult]:
        """Perform semantic search for the given query text."""
        query_embedding = await self.embedder.generate_embedding(query_text)
        results = await self.search_repo.semantic_search(query_embedding, top_k=top_k)
        return [
            VectorSearchResult(
                chunk_id=res.chunk_id,
                context=res.context,
                content=res.content,
                doc_id=res.doc_id,
                doc_name=res.doc_name,
                similarity_score=res.similarity_score,
            )
            for res in results
        ]

    async def semantic_search_with_rerank(
        self,
        query_text: str,
        top_k: int = 5,
        *,
        initial_k: int | None = None,
    ) -> list[VectorSearchResult]:
        """Perform semantic search and rerank the candidates using an LLM judge."""
        initial_limit = initial_k or max(top_k * 2, top_k)
        base_results = await self.semantic_search(query_text, top_k=initial_limit)
        if not base_results:
            return []
        if not self._rerank_chain:
            return base_results[:top_k]

        try:
            rerank_payload = await self._rerank_chain.ainvoke(
                {
                    "query": query_text,
                    "candidates": self._format_candidates(base_results),
                    "top_k": top_k,
                }
            )
        except Exception as exc:
            logger.warning("LLM rerank failed, falling back to similarity scores: %s", exc)
            print("LLM rerank failed, falling back to similarity scores: %s" % exc)
            return base_results[:top_k]

        score_map = {item.chunk_id: item.relevance for item in rerank_payload.results}
        reranked = sorted(
            base_results,
            key=lambda result: (score_map.get(result.chunk_id, 0.0), result.similarity_score),
            reverse=True,
        )
        return reranked[:top_k]

    def _build_rerank_chain(self):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a ranking model. Given a user query and a list of retrieved passages, "
                        "assign each chunk_id a relevance score between 0 and 1. Only consider the provided text."
                    ),
                ),
                (
                    "human",
                    (
                        "User query:\n{query}\n\n"
                        "Candidates:\n{candidates}\n\n"
                        "Return the top {top_k} chunk_ids and scores as JSON."
                    ),
                ),
            ]
        )
        return prompt | self.rerank_llm.with_structured_output(_RerankResponse)

    def _format_candidates(self, results: list[VectorSearchResult], *, snippet_limit: int = 500) -> str:
        lines = []
        for idx, result in enumerate(results, start=1):
            snippet = self._shorten_text(result.content or result.context or "", limit=snippet_limit)
            lines.append(
                f"{idx}. chunk_id={result.chunk_id}, doc={result.doc_name!r}, similarity={result.similarity_score:.3f}\n"
                f"   Passage: {snippet}"
            )
        return "\n".join(lines)

    @staticmethod
    def _shorten_text(text: str, *, limit: int) -> str:
        collapsed = " ".join(text.split())
        if len(collapsed) <= limit:
            return collapsed
        return f"{collapsed[: limit - 3].rstrip()}..."
