from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine, ForeignKey, Table, text, LargeBinary, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from pgvector.sqlalchemy import Vector


Base = declarative_base()


class UploadedDocument(Base):
    __tablename__ = 'uploaded_documents'
    id = Column(Integer, primary_key=True, index=True)
    doc_name = Column(String, index=True)
    content = Column(Text)
    doc_size = Column(Integer)
    upload_date = Column(DateTime, default=datetime.now())
    doc_type = Column(String)
    
    # One-to-many relationship with Chunks
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(Integer, ForeignKey("uploaded_documents.id", ondelete="CASCADE"))
    chunk_order = Column(Integer)
    content = Column(Text)             # contextualized chunk text
    raw_content = Column(Text)         # raw editable text
    created_date = Column(DateTime, default=datetime.now(datetime.UTC))

    document = relationship("UploadedDocument", back_populates="chunks")
    embedding = relationship("Embedding", back_populates="chunk", uselist=False, cascade="all, delete-orphan")


class Embedding(Base):
    __tablename__ = "embeddings"

    # chunk_id is both PK and FK -> guarantees one-to-one
    chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True)

    embedding = Column(Vector)       
    tfidf_embedding = Column(Vector) 

    created_date = Column(DateTime, default=datetime.now(datetime.UTC))

    chunk = relationship("Chunk", back_populates="embedding", uselist=False)