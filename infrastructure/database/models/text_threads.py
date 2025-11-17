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
from infrastructure.database.models.tenancy import Tenant, Project
from infrastructure.database.models.user_product import UserProduct


class TextThread(Base):
    __tablename__ = "text_threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    owner_user_id = Column(String(255), nullable=False, index=True)
    user_product_id = Column(Integer, ForeignKey("user_products.id", ondelete="SET NULL"), nullable=True, index=True)
    source_system = Column(String(120), nullable=False)
    external_thread_id = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    thread_text = Column(Text, nullable=False)
    message_count = Column(Integer, nullable=False, default=0)
    thread_started_at = Column(DateTime(timezone=True), nullable=True)
    thread_closed_at = Column(DateTime(timezone=True), nullable=True)
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
    product = relationship(UserProduct)
    messages = relationship("TextThreadMessage", back_populates="thread", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "project_id",
            "source_system",
            "external_thread_id",
            name="uq_text_threads_source_external",
        ),
    )


class TextThreadMessage(Base):
    __tablename__ = "text_thread_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(Integer, ForeignKey("text_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    sender_user_id = Column(String(255), nullable=True, index=True)
    sender_display_name = Column(String(255), nullable=True)
    sender_type = Column(String(50), nullable=True)
    position = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    raw_payload = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
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

    thread = relationship("TextThread", back_populates="messages")
    tenant = relationship(Tenant)
    project = relationship(Project)

    __table_args__ = (
        UniqueConstraint("thread_id", "position", name="uq_text_thread_messages_position"),
    )
