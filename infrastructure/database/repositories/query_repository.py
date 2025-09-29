from typing import List, Tuple
from sqlalchemy.orm import Session
from infrastructure.database.models.queries import Query, Response, Source
from infrastructure.database.models.documents import Chunk, UploadedDocument, Embedding
from sqlalchemy import and_

class QueryRepository:
    """Repository pattern for query-related database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_query(self, query_text: str) -> Query:
        """Create a new query entry in the database"""
        new_query = Query(query_text=query_text)
        self.db.add(new_query)
        self.db.commit()
        self.db.refresh(new_query)
        return new_query
    
    def get_query_by_id(self, query_id: int) -> Query:
        """Retrieve a query by its ID"""
        return self.db.query(Query).filter(Query.id == query_id).first()
    
    def get_all_queries(self) -> List[Query]:
        """Retrieve all queries from the database"""
        return self.db.query(Query).all()
    
    def create_response(self, query_id: int, response_text: str, status: str = 'pending') -> Response:
        """Create a response linked to a specific query"""
        new_response = Response(query_id=query_id, response_text=response_text, status=status)
        self.db.add(new_response)
        self.db.commit()
        self.db.refresh(new_response)
        return new_response
    
    def update_response_status(self, response_id: int, status: str) -> Response:
        """Update the status of a response"""
        response = self.db.query(Response).filter(Response.id == response_id).first()
        if response:
            response.status = status
            self.db.commit()
            self.db.refresh(response)
        return response
    
    def add_source(self, response_id: int, chunk_id: int, doc_id: int, doc_name: str, snippet: str) -> Source:
        """Add a source to a specific response"""
        new_source = Source(response_id=response_id, chunk_id=chunk_id, doc_id=doc_id, doc_name=doc_name, snippet=snippet)
        self.db.add(new_source)
        self.db.commit()
        self.db.refresh(new_source)
        return new_source
    
    def get_response_by_query_id(self, query_id: int) -> Response:
        """Retrieve the response associated with a specific query ID"""
        return self.db.query(Response).filter(Response.query_id == query_id).first()
    
    def get_sources(self, response_id: int) -> List[Source]:
        """Retrieve all sources linked to a specific response ID"""
        return self.db.query(Source).filter(Source.response_id == response_id).all()