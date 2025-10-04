from fastapi import APIRouter, Depends, HTTPException
from services.queries.query_service import QueryService
from infrastructure.context import RequestContextBundle
from routers.dependencies import get_request_context_bundle

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
            "sources": result["sources"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")