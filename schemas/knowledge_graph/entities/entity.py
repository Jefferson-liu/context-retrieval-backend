from pydantic import BaseModel, Field
import uuid
from schemas.knowledge_graph.entities.raw_entity import RawEntity
class Entity(BaseModel):
    """
    Model representing an entity (for entity resolution).
    'id' is the canonical entity id if this is a canonical entity.
    For extraction-time entities, we reuse the raw entity_idx so triplets can reference them.
    'resolved_id' is set to the canonical id if this is an alias.
    """

    id: int | uuid.UUID = Field(default_factory=uuid.uuid4)
    event_id: uuid.UUID | None = None
    name: str
    type: str
    description: str
    resolved_id: uuid.UUID | None = None

    @classmethod
    def from_raw(cls, raw_entity: "RawEntity", event_id: uuid.UUID | None = None) -> "Entity":
        """Create an Entity instance from a RawEntity, optionally associating it with an event_id."""
        return cls(
            id=raw_entity.entity_idx if raw_entity.entity_idx is not None else uuid.uuid4(),
            event_id=event_id,
            name=raw_entity.name,
            type=raw_entity.type,
            description=raw_entity.description,
            resolved_id=None,
        )
