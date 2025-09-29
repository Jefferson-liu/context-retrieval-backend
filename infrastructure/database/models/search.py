from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine, ForeignKey, Table, text, LargeBinary, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from pgvector.sqlalchemy import Vector

Base = declarative_base()
class Queries(Base):
    __tablename__ = 'queries'
    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False)
    response = relationship("Response", back_populates="query", uselist=False, cascade="all, delete-orphan")
    created_date = Column(DateTime, default=datetime.now())
    
class Response(Base):
    __tablename__ = 'responses'
    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(Integer, ForeignKey('queries.id', ondelete='CASCADE'), unique=True)
    response_text = Column(Text)
    status = Column(String, default='pending')  # 'pending', 'success', 'failed'
    created_date = Column(DateTime, default=datetime.now())
    
    query = relationship("Queries", back_populates="response")