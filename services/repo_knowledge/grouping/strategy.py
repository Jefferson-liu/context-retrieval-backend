from __future__ import annotations

from abc import ABC, abstractmethod

from services.repo_knowledge.grouping.types import GroupBuildResult, GroupFileEdge, GroupFileNode


class GroupingStrategy(ABC):
    """Strategy interface for deterministic file-summary grouping."""

    @abstractmethod
    def build_groups(self, *, file_nodes: list[GroupFileNode], file_edges: list[GroupFileEdge]) -> GroupBuildResult:
        """Build deterministic groups from file nodes and file-level edges."""
