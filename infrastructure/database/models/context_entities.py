from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from infrastructure.database.database import Base
from infrastructure.database.models.documents import Document
from infrastructure.database.models.tenancy import Project, Tenant
from infrastructure.database.models.text_threads import TextThread


class ContextEntity(Base):
    __tablename__ = "context_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    entity_type = Column(String(120), nullable=False)
    entity_identifier = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = relationship(Tenant)
    project = relationship(Project)
    document_links = relationship(
        "ContextEntityDocumentLink",
        back_populates="entity",
        cascade="all, delete-orphan",
    )
    thread_links = relationship(
        "ContextEntityThreadLink",
        back_populates="entity",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "entity_type",
            "entity_identifier",
            name="uq_context_entity_scope_identifier",
        ),
    )


class ContextEntityDocumentLink(Base):
    __tablename__ = "context_entity_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    context_entity_id = Column(
        Integer,
        ForeignKey("context_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    association_type = Column(String(120), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    entity = relationship("ContextEntity", back_populates="document_links")
    document = relationship(Document)

    __table_args__ = (
        UniqueConstraint("context_entity_id", "document_id", name="uq_context_entity_document"),
    )


class ContextEntityThreadLink(Base):
    __tablename__ = "context_entity_threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    context_entity_id = Column(
        Integer,
        ForeignKey("context_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text_thread_id = Column(
        Integer,
        ForeignKey("text_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    association_type = Column(String(120), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    entity = relationship("ContextEntity", back_populates="thread_links")
    text_thread = relationship(TextThread)

    __table_args__ = (
        UniqueConstraint("context_entity_id", "text_thread_id", name="uq_context_entity_thread"),
    )
