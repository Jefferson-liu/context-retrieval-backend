from pydantic import BaseModel
class Source(BaseModel):
    doc_id: int
    chunk_id: int
    content: str
    doc_name: str