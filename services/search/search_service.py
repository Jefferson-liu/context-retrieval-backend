from infrastructure.database.repositories.vector_search_repository import SearchRepository
from infrastructure.ai.embedding import Embedder
from sqlalchemy.ext.asyncio import AsyncSession
from schemas import VectorSearchResult
from langchain_anthropic import ChatAnthropic
from config import settings

class SearchService:
    def __init__(self, db: AsyncSession, context):
        self.db = db
        self.context = context
        self.search_repo = SearchRepository(db, context)
        self.embedder = Embedder(ChatAnthropic(temperature=0, model_name="claude-3-5-sonnet-latest", api_key=settings.ANTHROPIC_API_KEY))

    async def semantic_search(self, query_text: str, top_k: int = 5) -> list[VectorSearchResult]:
        """Perform semantic search for the given query text."""
        query_embedding = await self.embedder.generate_embedding(query_text)
        results = await self.search_repo.semantic_search(query_embedding, top_k=top_k)
        vector_search_results = [
            VectorSearchResult(
                chunk_id=res.chunk_id,
                context=res.context,
                content=res.content,
                doc_id=res.doc_id,
                doc_name=res.doc_name,
                similarity_score=res.similarity_score
            ) for res in results
        ]
        return vector_search_results