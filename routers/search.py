from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from infrastructure.database.repositories.search_repository import SearchRepository
from services.queries.query_service import QueryService
from infrastructure.database.database import get_db
from infrastructure.ai.embedding import Embedder
from typing import List, Dict

router = APIRouter()

@router.post("/search/semantic", summary="Perform semantic search")
async def semantic_search(
    query: str,
    top_k: int = 10,
    db: Session = Depends(get_db)
):
    """
    Search for relevant chunks using semantic similarity.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        repo = SearchRepository(db)
        embedder = Embedder()  # From infrastructure.ai.embedding
        query_embedding = await embedder.generate_embedding(query)
        
        results = repo.semantic_vector_search(query_embedding, top_k)
        
        return {
            "query": query,
            "results": [
                {
                    "id": r.id,
                    "content": r.content,
                    "filename": r.filename,
                    "similarity_score": r.similarity_score
                } for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.post("/search/tfidf", summary="Perform TF-IDF search")
async def tfidf_search(
    query: str,
    top_k: int = 10,
    db: Session = Depends(get_db)
):
    """
    Search for relevant chunks using TF-IDF similarity.
    Note: Requires fitted TF-IDF vectorizer (placeholder).
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        repo = SearchRepository(db)
        # Placeholder: Implement TF-IDF query vector generation
        # vectorizer = load_fitted_vectorizer()
        # query_vector = vectorizer.transform([query]).toarray()[0].tolist()
        query_vector = []  # Replace with actual vector
        
        results = repo.tfidf_similarity_search(query_vector, top_k)
        
        return {
            "query": query,
            "results": [
                {
                    "id": r.id,
                    "content": r.content,
                    "filename": r.filename,
                    "similarity_score": r.similarity_score
                } for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.post("/query", summary="Submit a query and get response")
async def submit_query(
    query_text: str,
    db: Session = Depends(get_db)
):
    """
    Submit a user query, process it, and return a response with sources.
    """
    if not query_text.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        service = QueryService(db)
        result = await service.process_query(query_text)
        
        return {
            "query": query_text,
            "response": result["response"],
            "sources": result["sources"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")