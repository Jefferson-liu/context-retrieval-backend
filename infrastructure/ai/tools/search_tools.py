import json

from langchain.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from services.search.search_service import SearchService
from services.document.retrieval import DocumentRetrievalService


def create_toolset(db: AsyncSession, context: ContextScope):
    """Instantiate search/document tools bound to the given database session/context."""
    search_service = SearchService(db, context)
    document_service = DocumentRetrievalService(db, context)

    @tool("search_chunks", return_direct=False)
    async def search_chunks(query: str) -> str:
        """Returns relevant document chunks for a given query. This does semantic search so it works best with short direct queries."""
        results = await search_service.semantic_search(query)
        payload = [{
            "chunk_id": result.chunk_id,
            "doc_id": result.doc_id,
            "content": result.context + "\n\n" + result.content,
        } for result in results]

        return json.dumps(payload)

    @tool("list_documents", return_direct=False)
    async def list_documents() -> str:
        """Lists all documents in the database."""
        documents = await document_service.list_documents()
        payload = [
            {
                "id": doc.id,
                "name": doc.doc_name,
            }
            for doc in documents
        ]
        return json.dumps(payload)

    @tool("get_document_chunks", return_direct=False)
    async def get_document_chunks(document_id: int) -> str:
        """Retrieves chunks for a specific document by its ID."""
        chunks = await document_service.get_document_chunks(document_id)
        payload = [
            {
                "id": chunk.id,
                "document_id": chunk.doc_id,
                "content": chunk.context + "\n\n" + chunk.content,
            }
            for chunk in chunks
        ]
        return json.dumps(payload)

    return [search_chunks, list_documents, get_document_chunks]

