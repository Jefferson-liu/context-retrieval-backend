from pydantic import BaseModel
from schemas.knowledge_graph.triplets.raw_triplet import RawTriplet
from schemas.knowledge_graph.entities.raw_entity import RawEntity
class RawExtraction(BaseModel):
    """Model representing a triplet extraction."""

    triplets: list[RawTriplet]
    entities: list[RawEntity]