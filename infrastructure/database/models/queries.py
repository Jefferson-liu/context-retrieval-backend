from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from infrastructure.database.database import Base
from infrastructure.database.models.tenancy import Tenant, Project

class Query(Base):
    __tablename__ = 'queries'
    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False)
    created_date = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='RESTRICT'), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    
    response = relationship("Response", back_populates="query", uselist=False, cascade="all, delete-orphan")
    tenant = relationship(Tenant)
    project = relationship(Project)
    
class Response(Base):
    __tablename__ = 'responses'
    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(Integer, ForeignKey('queries.id', ondelete='CASCADE'), unique=True)
    response_text = Column(Text)
    status = Column(String, default='pending')  # 'pending', 'success', 'failed'
    created_date = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='RESTRICT'), nullable=False, index=True)

    query = relationship("Query", back_populates="response")
    sources = relationship("Source", back_populates="response", cascade="all, delete-orphan")
    tenant = relationship(Tenant)
    project = relationship(Project)
    
    
class Source(Base):
    __tablename__ = 'sources'
    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey('responses.id', ondelete='CASCADE')) # ID of the response this source is linked to
    chunk_id = Column(Integer, ForeignKey('chunks.id', ondelete='SET NULL'), nullable=True)  # ID of the chunk used as a source
    doc_id = Column(Integer)    # ID of the document the chunk belongs to
    doc_name = Column(String)   # Name of the document
    snippet = Column(Text)      # Text snippet from the chunk
    created_date = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='RESTRICT'), nullable=False, index=True)
    
    response = relationship("Response", back_populates="sources")
    chunk = relationship("Chunk", primaryjoin="and_(Source.chunk_id==Chunk.id, Source.doc_id==Chunk.doc_id)", viewonly=True)
    tenant = relationship(Tenant)
    project = relationship(Project)
    
