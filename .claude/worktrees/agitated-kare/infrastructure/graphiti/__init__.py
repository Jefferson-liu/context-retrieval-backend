"""Graphiti client utilities and ontology definitions."""

from .graphiti_client import get_graphiti_client, ensure_bootstrap, build_group_id
from .ontology import (
    DEFAULT_ENTITY_TYPES,
    DEFAULT_EDGE_TYPES,
    DEFAULT_EDGE_TYPE_MAP,
    DEFAULT_EXCLUDED_ENTITY_TYPES,
)

__all__ = [
    "get_graphiti_client",
    "ensure_bootstrap",
    "DEFAULT_ENTITY_TYPES",
    "DEFAULT_EDGE_TYPES",
    "DEFAULT_EDGE_TYPE_MAP",
    "DEFAULT_EXCLUDED_ENTITY_TYPES",
    "build_group_id",
]
