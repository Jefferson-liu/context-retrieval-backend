import json
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.ai.embedding import Embedder
from infrastructure.context import ContextScope
from infrastructure.database.repositories.chunk_repository import ChunkRepository
from infrastructure.database.repositories.document_repository import DocumentRepository
from infrastructure.database.repositories.knowledge_event_repository import KnowledgeEventRepository
from infrastructure.database.repositories.knowledge_temporal_repository import KnowledgeStatementRepository


async def _build_event_payload(
    events,
    *,
    statement_repo: KnowledgeStatementRepository,
    chunk_repo: ChunkRepository,
    document_repo: DocumentRepository,
) -> List[Dict[str, Any]]:
    statement_ids = [str(event.statement_id) for event in events if getattr(event, "statement_id", None)]
    statement_map = await statement_repo.list_statements_by_ids(statement_ids)

    chunk_ids = [event.chunk_id for event in events if getattr(event, "chunk_id", None)]
    chunk_map = await chunk_repo.get_chunks_by_ids(chunk_ids)

    doc_ids = set()
    for statement in statement_map.values():
        if getattr(statement, "document_id", None):
            doc_ids.add(statement.document_id)
    for chunk in chunk_map.values():
        if getattr(chunk, "doc_id", None):
            doc_ids.add(chunk.doc_id)
    document_map = await document_repo.get_documents_by_ids(doc_ids)

    payload: List[Dict[str, Any]] = []
    for event in events:
        statement = statement_map.get(str(getattr(event, "statement_id", None)))
        chunk = chunk_map.get(getattr(event, "chunk_id", None))

        doc_id: Optional[int] = None
        if statement and getattr(statement, "document_id", None):
            doc_id = statement.document_id
        if doc_id is None and chunk and getattr(chunk, "doc_id", None):
            doc_id = chunk.doc_id
        doc_name = document_map.get(doc_id).doc_name if doc_id and doc_id in document_map else None

        payload.append(
            {
                "event_id": str(getattr(event, "id", None)),
                "statement_id": str(getattr(event, "statement_id", None)),
                "statement": getattr(statement, "statement", None),
                "valid_at": getattr(event, "valid_at", None) or getattr(statement, "valid_at", None),
                "invalid_at": getattr(event, "invalid_at", None) or getattr(statement, "invalid_at", None),
                "doc_id": doc_id,
                "doc_name": doc_name,
                "chunk_id": getattr(event, "chunk_id", None),
                "triplets": getattr(event, "triplets", None),
            }
        )
    return payload


def create_kg_toolset(db: AsyncSession, context: ContextScope):
    """Instantiate tools for knowledge graph search."""
    embedder = Embedder()
    event_repo = KnowledgeEventRepository(db, context)
    statement_repo = KnowledgeStatementRepository(db, context)
    chunk_repo = ChunkRepository(db, context)
    document_repo = DocumentRepository(db, context)

    @tool("search_knowledge_graph", return_direct=False)
    async def search_knowledge_graph(query: str, top_k: int = 5) -> str:
        """Returns knowledge graph events relevant to a query using statement embedding similarity."""
        query_embedding = await embedder.generate_embedding(query)
        events = await event_repo.semantic_search(query_embedding, top_k=top_k)
        if not events:
            return "[]"

        payload = await _build_event_payload(
            events,
            statement_repo=statement_repo,
            chunk_repo=chunk_repo,
            document_repo=document_repo,
        )
        return json.dumps(payload, default=str)

    return {
        "search_knowledge_graph": search_knowledge_graph,
    }
