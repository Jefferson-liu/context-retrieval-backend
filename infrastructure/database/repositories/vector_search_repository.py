from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope
from infrastructure.database.repositories import DocumentRepository, QueryRepository
from infrastructure.vector_store import create_vector_store

class SearchRepository:
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
        self.vector_store = create_vector_store(db)

    async def semantic_search(self, query_vector, top_k=10):
        """Search for the most similar chunks based on a query vector."""
        return await self.vector_store.search(
            query_vector,
            tenant_id=self.context.tenant_id,
            project_ids=self.context.project_ids,
            user_id=self.context.user_id,
            top_k=top_k,
        )
    
