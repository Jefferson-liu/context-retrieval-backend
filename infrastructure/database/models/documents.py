from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from pgvector.sqlalchemy import Vector

from config import settings
from infrastructure.database.database import Base
from infrastructure.database.models.tenancy import Tenant, Project


class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True, index=True)
    doc_name = Column(String, index=True)
    content = Column(Text)
    doc_size = Column(Integer)
    upload_date = Column(DateTime, default=datetime.now())
    doc_type = Column(String)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_user_id = Column(String, nullable=False)
    
    # One-to-many relationship with Chunks
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    tenant = relationship(Tenant)
    project = relationship(Project)

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_order = Column(Integer)
    context = Column(Text)             # contextualized chunk text
    content = Column(Text)         # raw editable text
    created_date = Column(DateTime, default=datetime.now())
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_user_id = Column(String, nullable=False)

    document = relationship("Document", back_populates="chunks")
    embedding = relationship("Embedding", back_populates="chunk", uselist=False, cascade="all, delete-orphan")
    tenant = relationship(Tenant)
    project = relationship(Project)


class Embedding(Base):
    __tablename__ = "embeddings"

    # chunk_id is both PK and FK -> guarantees one-to-one
    chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True)

    embedding = Column(Vector(settings.EMBEDDING_VECTOR_DIM))
    created_date = Column(DateTime, default=datetime.now())
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)

    chunk = relationship("Chunk", back_populates="embedding", uselist=False)
    tenant = relationship(Tenant)
    project = relationship(Project)