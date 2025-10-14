from datetime import datetime

from sqlalchemy import (
	Column,
	DateTime,
	ForeignKey,
	Integer,
	String,
	Text,
	UniqueConstraint,
	Float,
)
from sqlalchemy.orm import relationship

from infrastructure.database.database import Base
from infrastructure.database.models.tenancy import Tenant, Project


class KnowledgeEntity(Base):
	__tablename__ = "knowledge_entities"

	id = Column(Integer, primary_key=True, index=True)
	tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
	project_id = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
	name = Column(String(255), nullable=False)
	entity_type = Column(String(100), nullable=False)
	description = Column(Text, nullable=True)
	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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

	__table_args__ = (
		UniqueConstraint(
			"tenant_id",
			"project_id",
			"name",
			"entity_type",
			name="uq_knowledge_entity_name_type",
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
	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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
	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

	tenant = relationship(Tenant)
	project = relationship(Project)
	relationship = relationship("KnowledgeRelationship", back_populates="metadata_entries")

	__table_args__ = (
		UniqueConstraint("relationship_id", "key", name="uq_relationship_metadata_key"),
	)
