from datetime import datetime, timezone
import uuid

from sqlalchemy import (
		Column,
		DateTime,
		ForeignKey,
		Integer,
		String,
		Text,
		UniqueConstraint,
		Float,
		Index,
		JSON,
	)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from infrastructure.database.database import Base
from pgvector.sqlalchemy import Vector
from config import settings
from infrastructure.database.models.tenancy import Tenant, Project


class KnowledgeEntity(Base):
	__tablename__ = "knowledge_entities"

	id = Column(Integer, primary_key=True, index=True)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	name = Column(String(255), nullable=False)
	canonical_name = Column(String(255), nullable=False, index=True)
	entity_type = Column(String(100), nullable=False)
	description = Column(Text, nullable=True)
	event_id = Column(PGUUID(as_uuid=True), ForeignKey("knowledge_events.id", ondelete="SET NULL"), nullable=True, index=True)
	resolved_id = Column(Integer, ForeignKey("knowledge_entities.id", ondelete="SET NULL"), nullable=True, index=True)
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
	outgoing_relationships = relationship(
		"KnowledgeRelationship",
		foreign_keys="KnowledgeRelationship.source_entity_id",
		back_populates="source_entity",
	)
	incoming_relationships = relationship(
		"KnowledgeRelationship",
		foreign_keys="KnowledgeRelationship.target_entity_id",
		back_populates="target_entity",
	)
	aliases = relationship(
		"KnowledgeEntityAlias",
		back_populates="entity",
		cascade="all, delete-orphan",
	)
	event = relationship("KnowledgeEvent", foreign_keys=[event_id])
	resolved_entity = relationship("KnowledgeEntity", remote_side=[id], foreign_keys=[resolved_id])

	__table_args__ = (
		UniqueConstraint(
			"tenant_id",
			"project_id",
			"name",
			"entity_type",
			name="uq_knowledge_entity_name_type",
		),
		Index(
			"ix_knowledge_entities_canonical",
			"tenant_id",
			"project_id",
			"entity_type",
			"canonical_name",
			unique=True,
		),
	)


class KnowledgeRelationship(Base):
	__tablename__ = "knowledge_relationships"

	id = Column(Integer, primary_key=True, index=True)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	source_entity_id = Column(
		Integer,
		ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	target_entity_id = Column(
		Integer,
		ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	relationship_type = Column(String(120), nullable=False)
	description = Column(Text, nullable=True)
	confidence = Column(Float, nullable=True)
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
	source_entity = relationship(
		"KnowledgeEntity",
		foreign_keys=[source_entity_id],
		back_populates="outgoing_relationships",
	)
	target_entity = relationship(
		"KnowledgeEntity",
		foreign_keys=[target_entity_id],
		back_populates="incoming_relationships",
	)
	metadata_entries = relationship(
		"KnowledgeRelationshipMetadata",
		back_populates="relationship",
		cascade="all, delete-orphan",
	)

	__table_args__ = (
		UniqueConstraint(
			"tenant_id",
			"project_id",
			"source_entity_id",
			"target_entity_id",
			"relationship_type",
			name="uq_knowledge_relationship_unique",
		),
	)


class KnowledgeRelationshipMetadata(Base):
	__tablename__ = "knowledge_relationship_metadata"

	id = Column(Integer, primary_key=True, index=True)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	relationship_id = Column(
		Integer,
		ForeignKey("knowledge_relationships.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	key = Column(String(100), nullable=False)
	value = Column(Text, nullable=True)
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
	relationship = relationship("KnowledgeRelationship", back_populates="metadata_entries")

	__table_args__ = (
		UniqueConstraint("relationship_id", "key", name="uq_relationship_metadata_key"),
	)


class KnowledgeEntityAlias(Base):
	__tablename__ = "knowledge_entity_aliases"

	id = Column(Integer, primary_key=True, index=True)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	entity_id = Column(Integer, ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
	entity_type = Column(String(100), nullable=False, index=True)
	alias_name = Column(String(255), nullable=False)
	alias_canonical_name = Column(String(255), nullable=False, index=True)
	created_at = Column(
		DateTime(timezone=True),
		default=lambda: datetime.now(timezone.utc),
		nullable=False,
	)

	entity = relationship("KnowledgeEntity", back_populates="aliases")
	tenant = relationship(Tenant)
	project = relationship(Project)

	__table_args__ = (
		UniqueConstraint(
			"tenant_id",
			"project_id",
			"entity_type",
			"alias_canonical_name",
			name="uq_entity_alias_canonical",
		),
	)


class KnowledgeStatement(Base):
	__tablename__ = "knowledge_statements"

	id = Column(
		PGUUID(as_uuid=True),
		primary_key=True,
		default=uuid.uuid4,
	)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
	chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True, index=True)
	statement = Column(Text, nullable=False)
	statement_type = Column(String(32), nullable=False)
	temporal_type = Column(String(32), nullable=False)
	valid_at = Column(DateTime(timezone=True), nullable=True)
	invalid_at = Column(DateTime(timezone=True), nullable=True)
	embedding = Column(Vector(settings.EMBEDDING_VECTOR_DIM), nullable=True)
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
	document = relationship("Document")
	chunk = relationship("Chunk")
	triplets = relationship(
		"KnowledgeStatementTriplet",
		back_populates="statement",
		cascade="all, delete-orphan",
	)
	invalidation_requests = relationship(
		"KnowledgeStatementInvalidation",
		back_populates="statement",
		cascade="all, delete-orphan",
		foreign_keys="KnowledgeStatementInvalidation.statement_id",
	)

	__table_args__ = (
		Index("ix_knowledge_statements_valid_at", "valid_at"),
	)


class KnowledgeEvent(Base):
	__tablename__ = "knowledge_events"

	id = Column(
		PGUUID(as_uuid=True),
		primary_key=True,
		default=uuid.uuid4,
	)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True, index=True)
	statement_id = Column(
		PGUUID(as_uuid=True),
		ForeignKey("knowledge_statements.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	triplets = Column(JSON, nullable=False, default=list)
	valid_at = Column(DateTime(timezone=True), nullable=True)
	invalid_at = Column(DateTime(timezone=True), nullable=True)
	invalidated_by = Column(
		PGUUID(as_uuid=True),
		ForeignKey("knowledge_events.id", ondelete="SET NULL"),
		nullable=True,
		index=True,
	)
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
	chunk = relationship("Chunk")
	statement_ref = relationship("KnowledgeStatement")


class KnowledgeEventInvalidation(Base):
	__tablename__ = "knowledge_event_invalidations"

	id = Column(
		PGUUID(as_uuid=True),
		primary_key=True,
		default=uuid.uuid4,
	)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	event_id = Column(
		PGUUID(as_uuid=True),
		ForeignKey("knowledge_events.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	new_event_id = Column(
		PGUUID(as_uuid=True),
		ForeignKey("knowledge_events.id", ondelete="SET NULL"),
		nullable=True,
		index=True,
	)
	reason = Column(Text, nullable=True)
	suggested_invalid_at = Column(DateTime(timezone=True), nullable=True)
	status = Column(String(32), nullable=False, default="pending")
	approved_by = Column(String(255), nullable=True)
	approved_at = Column(DateTime(timezone=True), nullable=True)
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

	event = relationship(
		"KnowledgeEvent",
		foreign_keys=[event_id],
	)
	new_event = relationship(
		"KnowledgeEvent",
		foreign_keys=[new_event_id],
	)
	tenant = relationship(Tenant)
	project = relationship(Project)

	__table_args__ = (
		Index(
			"ix_event_invalidation_status",
			"tenant_id",
			"project_id",
			"status",
		),
	)


class KnowledgeEventInvalidationBatch(Base):
	__tablename__ = "knowledge_event_invalidation_batches"

	id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	status = Column(String(32), nullable=False, default="pending")
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
	approved_at = Column(DateTime(timezone=True), nullable=True)
	created_by = Column(String(255), nullable=True)
	approved_by = Column(String(255), nullable=True)

	tenant = relationship(Tenant)
	project = relationship(Project)
	items = relationship(
		"KnowledgeEventInvalidationBatchItem",
		back_populates="batch",
		cascade="all, delete-orphan",
	)


class KnowledgeEventInvalidationBatchItem(Base):
	__tablename__ = "knowledge_event_invalidation_batch_items"

	id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	batch_id = Column(PGUUID(as_uuid=True), ForeignKey("knowledge_event_invalidation_batches.id", ondelete="CASCADE"), nullable=False, index=True)
	event_id = Column(PGUUID(as_uuid=True), ForeignKey("knowledge_events.id", ondelete="CASCADE"), nullable=False, index=True)
	new_event_id = Column(PGUUID(as_uuid=True), ForeignKey("knowledge_events.id", ondelete="SET NULL"), nullable=True, index=True)
	reason = Column(Text, nullable=True)
	suggested_invalid_at = Column(DateTime(timezone=True), nullable=True)
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

	batch = relationship("KnowledgeEventInvalidationBatch", back_populates="items")
	event = relationship("KnowledgeEvent", foreign_keys=[event_id])
	new_event = relationship("KnowledgeEvent", foreign_keys=[new_event_id])
	tenant = relationship(Tenant)
	project = relationship(Project)


class KnowledgeStatementTriplet(Base):
	__tablename__ = "knowledge_statement_triplets"

	id = Column(
		PGUUID(as_uuid=True),
		primary_key=True,
		default=uuid.uuid4,
	)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	statement_id = Column(
		PGUUID(as_uuid=True),
		ForeignKey("knowledge_statements.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	subject_entity_id = Column(
		Integer,
		ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	object_entity_id = Column(
		Integer,
		ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	predicate = Column(String(120), nullable=False)
	value = Column(Text, nullable=True)
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

	statement = relationship(
		"KnowledgeStatement",
		back_populates="triplets",
	)
	subject_entity = relationship(
		"KnowledgeEntity",
		foreign_keys=[subject_entity_id],
	)
	object_entity = relationship(
		"KnowledgeEntity",
		foreign_keys=[object_entity_id],
	)

	__table_args__ = (
		Index(
			"ix_knowledge_statement_triplets_subject_object",
			"subject_entity_id",
			"object_entity_id",
		),
	)


class KnowledgeStatementInvalidation(Base):
	__tablename__ = "knowledge_statement_invalidations"

	id = Column(
		PGUUID(as_uuid=True),
		primary_key=True,
		default=uuid.uuid4,
	)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	statement_id = Column(
		PGUUID(as_uuid=True),
		ForeignKey("knowledge_statements.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	new_statement_id = Column(
		PGUUID(as_uuid=True),
		ForeignKey("knowledge_statements.id", ondelete="SET NULL"),
		nullable=True,
		index=True,
	)
	reason = Column(Text, nullable=True)
	suggested_invalid_at = Column(DateTime(timezone=True), nullable=True)
	status = Column(String(32), nullable=False, default="pending")
	approved_by = Column(String(255), nullable=True)
	approved_at = Column(DateTime(timezone=True), nullable=True)
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

	statement = relationship(
		"KnowledgeStatement",
		foreign_keys=[statement_id],
		back_populates="invalidation_requests",
	)
	new_statement = relationship(
		"KnowledgeStatement",
		foreign_keys=[new_statement_id],
	)
	tenant = relationship(Tenant)
	project = relationship(Project)

	__table_args__ = (
		Index(
			"ix_statement_invalidation_status",
			"tenant_id",
			"project_id",
			"status",
		),
	)
