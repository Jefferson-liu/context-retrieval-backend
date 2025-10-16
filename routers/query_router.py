from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from infrastructure.context import RequestContextBundle
from infrastructure.database.repositories.vector_search_repository import SearchRepository
from routers.dependencies import get_request_context_bundle
from schemas import VectorSearchResult
from services.queries.query_service import QueryService
from services.search.search_service import SearchService
from infrastructure.ai.embedding import Embedder


class VectorSearchTestRequest(BaseModel):
    query: str = Field(..., description="The user query text")
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of similar chunks to return",
    )


class VectorSearchTestResponse(BaseModel):
    results: list[VectorSearchResult]

router = APIRouter()

@router.post("/query", summary="Submit a query and get response")
async def submit_query(
    query_text: str,
    context_bundle: RequestContextBundle = Depends(get_request_context_bundle)
):
    """
    Submit a user query, process it, and return a response with sources.
    """
    if not query_text.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        service = QueryService(context_bundle.db, context_bundle.scope)
        result = await service.process_query(query_text)
        
        return {
            "query": query_text,
            "response": result["response"],
            "clauses": result["clauses"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@router.post(
    "/query/vector-search-test",
    summary="Run vector search with a query",
    response_model=VectorSearchTestResponse,
)
async def vector_search_test(
    request: VectorSearchTestRequest,
    context_bundle: RequestContextBundle = Depends(get_request_context_bundle),
) -> VectorSearchTestResponse:
    """
    Run a vector search test with the provided query text and return similar chunks.
    """
    service = SearchService(context_bundle.db, context_bundle.scope, Embedder())
    try:
        results = await service.semantic_search(request.query, top_k=request.top_k)
        
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vector search failed: {exc}") from exc

    return VectorSearchTestResponse(results=results)
