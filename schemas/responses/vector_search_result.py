from pydantic import BaseModel
class VectorSearchResult(BaseModel):
    chunk_id: int
    context: str
    content: str
    doc_id: int
    doc_name: str
    similarity_score: float