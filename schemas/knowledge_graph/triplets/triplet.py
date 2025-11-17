from pydantic import BaseModel, Field
import uuid
from schemas.knowledge_graph.predicate import Predicate
from schemas.knowledge_graph.triplets.raw_triplet import RawTriplet
class Triplet(BaseModel):
    """Model representing a subject-predicate-object triplet."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_id: uuid.UUID | None = None
    subject_name: str
    subject_id: int | uuid.UUID
    predicate: Predicate
    object_name: str
    object_id: int | uuid.UUID
    value: str | None = None

    # Compatibility aliases for code that expects *_entity_id fields.
    @property
    def subject_entity_id(self) -> int | uuid.UUID:
        return self.subject_id

    @property
    def object_entity_id(self) -> int | uuid.UUID:
        return self.object_id

    @classmethod
    def from_raw(cls, raw_triplet: "RawTriplet", event_id: uuid.UUID | None = None) -> "Triplet":
        """Create a Triplet instance from a RawTriplet, optionally associating it with an event_id."""
        return cls(
            id=uuid.uuid4(),
            event_id=event_id,
            subject_name=raw_triplet.subject_name,
            subject_id=raw_triplet.subject_id,
            predicate=raw_triplet.predicate,
            object_name=raw_triplet.object_name,
            object_id=raw_triplet.object_id,
            value=raw_triplet.value,
        )
