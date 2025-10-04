from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope
from infrastructure.database.models.documents import Embedding, Chunk


class ChunkRepository:
    """Repository pattern for Chunking and Embedding database operations"""
    
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
    
    async def create_chunk(self, doc_id: int, chunk_order: int, context_text: str, content: str) -> Chunk:
        """Create a new chunk record"""
        new_chunk = Chunk(
            doc_id=doc_id,
            chunk_order=chunk_order,
            context=context_text,
            content=content,
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            created_by_user_id=self.context.user_id,
        )
        self.db.add(new_chunk)
        await self.db.flush()
        return new_chunk

    async def create_embedding(self, chunk_id: int, embedding_vector: List[float]) -> Embedding:
        """Create a new embedding record"""
        new_embedding = Embedding(
            chunk_id=chunk_id,
            embedding=embedding_vector,
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
        )
        self.db.add(new_embedding)
        await self.db.flush()
        return new_embedding
    
    async def get_chunks_by_doc_id(self, doc_id: int) -> List[Chunk]:
        """Get all chunks associated with a specific document ID"""
        stmt = select(Chunk).where(
            Chunk.doc_id == doc_id,
            Chunk.tenant_id == self.context.tenant_id,
            Chunk.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_chunk_ids_by_doc_id(self, doc_id: int) -> List[int]:
        """Return chunk identifiers for a document within the current scope."""
        stmt = select(Chunk.id).where(
            Chunk.doc_id == doc_id,
            Chunk.tenant_id == self.context.tenant_id,
            Chunk.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]
    
    async def edit_chunk(self, chunk_id: int, **kwargs) -> Optional[Chunk]:
        """Edit an existing chunk record"""
        stmt = select(Chunk).where(
            Chunk.id == chunk_id,
            Chunk.tenant_id == self.context.tenant_id,
            Chunk.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        chunk = result.scalar_one_or_none()
        if chunk:
            for key, value in kwargs.items():
                if hasattr(chunk, key):
                    setattr(chunk, key, value)
        return chunk

    async def update_embedding(self, chunk_id: int, **kwargs) -> Optional[Embedding]:
        """Update the embedding for an existing record"""
        stmt = select(Embedding).where(
            Embedding.chunk_id == chunk_id,
            Embedding.tenant_id == self.context.tenant_id,
            Embedding.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        embedding = result.scalar_one_or_none()
        if embedding:
            for key, value in kwargs.items():
                if hasattr(embedding, key):
                    setattr(embedding, key, value)
        return embedding
    
    async def get_embedding_by_chunk_id(self, chunk_id: int) -> Optional[Embedding]:
        """Get a single embedding by chunk ID"""
        stmt = select(Embedding).where(
            Embedding.chunk_id == chunk_id,
            Embedding.tenant_id == self.context.tenant_id,
            Embedding.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_chunks_with_embeddings(self) -> List[Tuple]:
        stmt = (
            select(Chunk.id, Chunk.context, Embedding.embedding)
            .join(Embedding)
            .where(
                Chunk.tenant_id == self.context.tenant_id,
                Chunk.project_id.in_(self.context.project_ids),
            )
        )
        result = await self.db.execute(stmt)
        return result.all()
    
    async def delete_chunk(self, chunk_id: int) -> bool:
        """Delete a chunk by its ID"""
        stmt = select(Chunk).where(
            Chunk.id == chunk_id,
            Chunk.tenant_id == self.context.tenant_id,
            Chunk.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        chunk = result.scalar_one_or_none()
        if chunk:
            await self.db.delete(chunk)
            await self.db.commit()
            return True
        return False
    
    async def delete_chunks_by_doc_id(self, doc_id: int) -> int:
        """Delete chunks by document ID"""
        stmt = select(Chunk).where(
            Chunk.doc_id == doc_id,
            Chunk.tenant_id == self.context.tenant_id,
            Chunk.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        chunks = result.scalars().all()
        count = len(chunks)
        for chunk in chunks:
            await self.db.delete(chunk)
        await self.db.commit()
        return count
    
    
    
    