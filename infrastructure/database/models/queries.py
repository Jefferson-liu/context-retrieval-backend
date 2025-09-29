from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine, ForeignKey, Table, text, LargeBinary, Boolean
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from infrastructure.database.database import Base

class Query(Base):
    __tablename__ = 'queries'
    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False)
    created_date = Column(DateTime, default=datetime.now())
    
    response = relationship("Response", back_populates="query", uselist=False, cascade="all, delete-orphan")
    
class Response(Base):
    __tablename__ = 'responses'
    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(Integer, ForeignKey('queries.id', ondelete='CASCADE'), unique=True)
    response_text = Column(Text)
    status = Column(String, default='pending')  # 'pending', 'success', 'failed'
    created_date = Column(DateTime, default=datetime.now())

    query = relationship("Query", back_populates="response")
    sources = relationship("Source", back_populates="response", cascade="all, delete-orphan")
    
    
class Source(Base):
    __tablename__ = 'sources'
    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey('responses.id', ondelete='CASCADE')) # ID of the response this source is linked to
    chunk_id = Column(Integer)  # ID of the chunk used as a source
    doc_id = Column(Integer)    # ID of the document the chunk belongs to
    doc_name = Column(String)   # Name of the document
    snippet = Column(Text)      # Text snippet from the chunk
    created_date = Column(DateTime, default=datetime.now())
    
    response = relationship("Response", back_populates="sources", cascade="all, delete-orphan")
    chunk = relationship("Chunk", primaryjoin="and_(Source.chunk_id==Chunk.id, Source.doc_id==Chunk.doc_id)", viewonly=True)
    