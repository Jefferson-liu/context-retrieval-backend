from pydantic import BaseModel
from schemas.source import Source

class Clause(BaseModel):
    statement: str
    sources: list[Source]
    