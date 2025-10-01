from sqlalchemy.orm import Session
from infrastructure.database.repositories import DocumentRepository, SearchRepository, QueryRepository

class SearchService:
    def __init__(self, db: Session):
        self.db = db
        self.document_repository = DocumentRepository(db)
        self.search_repository = SearchRepository(db)
        self.query_repository = QueryRepository(db)
        
    def semantic_similarity_search(self, query_vector, top_k=10):
        """Search for the most similar chunks based on a query vector."""
        return self.search_repository.semantic_vector_search(query_vector, top_k)
    