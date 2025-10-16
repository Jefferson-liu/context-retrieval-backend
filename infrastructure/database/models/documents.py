from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    BigInteger,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY

from config import settings
from infrastructure.database.database import Base
from infrastructure.database.models.tenancy import Tenant, Project


class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True, index=True)
    doc_name = Column(String, index=True)
    context = Column(Text)
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
    summary = relationship("DocumentSummary", back_populates="document", uselist=False, cascade="all, delete-orphan")

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


# Backwards-compatible alias expected by legacy code and tests
UploadedDocument = Document


class DocumentSummary(Base):
    __tablename__ = "document_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    summary_text = Column(Text, nullable=False)
    summary_tokens = Column(Integer, nullable=True)
    summary_hash = Column(String(64), nullable=True, unique=False)
    milvus_primary_key = Column(BigInteger, nullable=True, unique=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship(Tenant)
    project = relationship(Project)
    document = relationship("Document", back_populates="summary", uselist=False)

    __table_args__ = (
        UniqueConstraint("document_id", name="uq_document_summary_document_id"),
        Index(
            "ix_document_summaries_tenant_project_document",
            "tenant_id",
            "project_id",
            "document_id",
        ),
        Index("ix_document_summaries_milvus_pk", "milvus_primary_key"),
    )


class ProjectSummary(Base):
    __tablename__ = "project_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    summary_tokens = Column(Integer, nullable=True)
    source_document_ids = Column(ARRAY(Integer), nullable=True)
    refreshed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship(Tenant)
    project = relationship(Project)

    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", name="uq_project_summary_tenant_project"),
    )
