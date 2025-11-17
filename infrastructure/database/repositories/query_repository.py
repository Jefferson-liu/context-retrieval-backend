from typing import Any, List, Optional, Sequence
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope
from infrastructure.database.models.queries import Query, Response, Source

class QueryRepository:
    """Repository pattern for query-related database operations"""
    
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
    
    async def create_query(self, query_text: str) -> Query:
        """Create a new query entry in the database"""
        new_query = Query(
            query_text=query_text,
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            user_id=self.context.user_id,
        )
        self.db.add(new_query)
        # Don't commit here, let the service handle transaction
        await self.db.flush()  # Assign ID
        return new_query
    
    async def get_query_by_id(self, query_id: int) -> Query:
        """Retrieve a query by its ID"""
        stmt = select(Query).where(
            Query.id == query_id,
            Query.tenant_id == self.context.tenant_id,
            Query.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all_queries(self) -> List[Query]:
        """Retrieve all queries from the database"""
        stmt = select(Query).where(
            Query.tenant_id == self.context.tenant_id,
            Query.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def create_response(self, query_id: int, response_text: str = None, status: str = 'pending') -> Response:
        """Create a response linked to a specific query"""
        new_response = Response(
            query_id=query_id,
            response_text=response_text,
            status=status,
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
        )
        self.db.add(new_response)
        # Don't commit here
        await self.db.flush()  # Assign ID
        return new_response
    
    async def update_response_status(self, response_id: int, status: str) -> Response:
        """Update the status of a response"""
        stmt = select(Response).where(
            Response.id == response_id,
            Response.tenant_id == self.context.tenant_id,
            Response.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        response = result.scalar_one_or_none()
        if response:
            response.status = status
            await self.db.flush()  # Ensure changes are sent to DB
        return response
    
    async def update_response_text(self, response_id: int, response_text: str) -> Response:
        """Update the text content of a response"""
        stmt = select(Response).where(
            Response.id == response_id,
            Response.tenant_id == self.context.tenant_id,
            Response.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        response = result.scalar_one_or_none()
        if response:
            response.response_text = response_text
            await self.db.flush()  # Ensure changes are sent to DB
        return response
    
    async def add_source(self, response_id: int, chunk_id: int, doc_id: int, doc_name: str, snippet: str) -> Source:
        """Add a source to a specific response"""
        new_source = Source(
            response_id=response_id,
            chunk_id=chunk_id,
            doc_id=doc_id,
            doc_name=doc_name,
            snippet=snippet,
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
        )
        self.db.add(new_source)
        # Don't commit here
        return new_source

    async def add_sources_bulk(self, response_id: int, payloads: Sequence[dict[str, Any]]) -> None:
        """Bulk insert sources for a response."""
        if not payloads:
            return

        values = [
            {
                "response_id": response_id,
                "chunk_id": payload.get("chunk_id"),
                "doc_id": payload.get("doc_id"),
                "doc_name": payload.get("doc_name"),
                "snippet": payload.get("snippet"),
                "tenant_id": self.context.tenant_id,
                "project_id": self.context.primary_project(),
            }
            for payload in payloads
        ]

        stmt = insert(Source).values(values)
        await self.db.execute(stmt)
    
    async def get_response_by_query_id(self, query_id: int) -> Optional[Response]:
        """Retrieve the response associated with a specific query ID"""
        stmt = select(Response).where(
            Response.query_id == query_id,
            Response.tenant_id == self.context.tenant_id,
            Response.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_sources(self, response_id: int) -> List[Source]:
        """Retrieve all sources linked to a specific response ID"""
        stmt = select(Source).where(
            Source.response_id == response_id,
            Source.tenant_id == self.context.tenant_id,
            Source.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
