from __future__ import annotations

from collections import Counter, defaultdict
from math import ceil
import re
from uuid import NAMESPACE_URL, uuid5

from services.repo_knowledge.grouping.strategy import GroupingStrategy
from services.repo_knowledge.grouping.types import BuiltGroup, GroupBuildResult, GroupFileEdge, GroupFileNode, GroupMember

LAYER_HINTS = {
    "routers": "api",
    "services": "service",
    "infrastructure": "infrastructure",
    "schemas": "schema",
    "tests": "test",
    "scripts": "script",
}
ENTRYPOINT_TOKENS = {
    "main",
    "app",
    "server",
    "index",
    "entry",
    "router",
    "api",
    "cli",
}
INFRA_TOKENS = {"util", "helper", "common", "shared", "base", "config", "test"}
TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


class AdaptiveDependencyRepoManager(GroupingStrategy):
    """Build balanced file-summary segments using dependency traversal and token caps."""

    def __init__(
        self,
        *,
        max_group_tokens: int,
        representative_count: int,
    ) -> None:
        self.max_group_tokens = max(1, max_group_tokens)
        self.representative_count = max(1, representative_count)

    def build_groups(self, *, file_nodes: list[GroupFileNode], file_edges: list[GroupFileEdge]) -> GroupBuildResult:
        if not file_nodes:
            return GroupBuildResult(groups=[], members_seen=0)

        node_by_id = {node.subject_id: node for node in file_nodes}
        valid_ids = set(node_by_id)
        filtered_edges = [
            edge for edge in file_edges if edge.from_subject_id in valid_ids and edge.to_subject_id in valid_ids
        ]
        estimated_tokens = {
            node.subject_id: _estimate_summary_tokens(node)
            for node in file_nodes
        }
        total_tokens = sum(estimated_tokens.values())
        group_count = max(1, ceil(total_tokens / self.max_group_tokens))
        target_tokens = max(1, ceil(total_tokens / group_count))

        ordered_ids = _dependency_order(node_by_id=node_by_id, file_edges=filtered_edges)
        grouped_ids = _balanced_partition(
            ordered_ids=ordered_ids,
            estimated_tokens=estimated_tokens,
            target_tokens=target_tokens,
            group_count=group_count,
        )
        neighbor_groups = _group_neighbors(grouped_ids=grouped_ids, file_edges=filtered_edges)

        groups: list[BuiltGroup] = []
        for index, member_ids in enumerate(grouped_ids, start=1):
            if not member_ids:
                continue
            member_paths = [node_by_id[subject_id].subject_path for subject_id in member_ids]
            layer_hint = _infer_layer_hint(member_paths)
            group_key = f"segment_{index:03d}"
            group_label = f"Repo Manager Segment {index}"
            internal_degree = _internal_degrees(member_ids=set(member_ids), file_edges=filtered_edges)
            representatives = _select_representatives(
                member_ids=member_ids,
                node_by_id=node_by_id,
                internal_degree=internal_degree,
                representative_count=self.representative_count,
            )
            representative_set = set(representatives)
            ranked_members = _rank_members(
                member_ids=member_ids,
                node_by_id=node_by_id,
                internal_degree=internal_degree,
                representative_set=representative_set,
            )
            group_id = str(uuid5(NAMESPACE_URL, f"{group_key}|{'|'.join(member_ids)}"))
            groups.append(
                BuiltGroup(
                    group_id=group_id,
                    group_key=group_key,
                    group_label=group_label,
                    layer_hint=layer_hint,
                    member_count=len(member_ids),
                    dependency_neighbor_count=len(neighbor_groups.get(group_key, set())),
                    is_infrastructure_seed=_is_infrastructure_seed(member_paths),
                    heuristics={
                        "strategy": "adaptive_dependency_repo_manager",
                        "group_index": index,
                        "group_count": group_count,
                        "target_tokens": target_tokens,
                        "max_group_tokens": self.max_group_tokens,
                        "estimated_group_tokens": sum(estimated_tokens[subject_id] for subject_id in member_ids),
                        "member_paths": member_paths,
                    },
                    representative_subject_ids=representatives,
                    members=ranked_members,
                )
            )

        return GroupBuildResult(groups=groups, members_seen=sum(group.member_count for group in groups))


def _estimate_summary_tokens(node: GroupFileNode) -> int:
    text = " ".join(
        part
        for part in [
            node.subject_path,
            node.overall_summary,
            node.group_function or "",
            " ".join(node.important_relationships),
        ]
        if part
    )
    return max(40, ceil(len(text) / 4))


def _dependency_order(*, node_by_id: dict[str, GroupFileNode], file_edges: list[GroupFileEdge]) -> list[str]:
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming_count: dict[str, int] = {subject_id: 0 for subject_id in node_by_id}
    for edge in file_edges:
        outgoing[edge.from_subject_id].add(edge.to_subject_id)
        incoming_count[edge.to_subject_id] = incoming_count.get(edge.to_subject_id, 0) + 1

    def priority(subject_id: str) -> tuple[int, int, str]:
        path = node_by_id[subject_id].subject_path
        tokens = set(_tokenize(path.rsplit("/", 1)[-1].rsplit(".", 1)[0]))
        entry_score = 1 if tokens & ENTRYPOINT_TOKENS else 0
        return (-entry_score, incoming_count.get(subject_id, 0), path)

    visited: set[str] = set()
    ordered: list[str] = []

    def dfs(subject_id: str) -> None:
        if subject_id in visited:
            return
        visited.add(subject_id)
        ordered.append(subject_id)
        for neighbor in sorted(outgoing.get(subject_id, set()), key=lambda item: node_by_id[item].subject_path):
            dfs(neighbor)

    roots = sorted(node_by_id, key=priority)
    for subject_id in roots:
        dfs(subject_id)
    return ordered


def _balanced_partition(
    *,
    ordered_ids: list[str],
    estimated_tokens: dict[str, int],
    target_tokens: int,
    group_count: int,
) -> list[list[str]]:
    groups: list[list[str]] = []
    current_group: list[str] = []
    current_tokens = 0

    for index, subject_id in enumerate(ordered_ids):
        remaining_items = len(ordered_ids) - index
        remaining_groups = max(1, group_count - len(groups))
        item_tokens = estimated_tokens[subject_id]
        should_close = (
            bool(current_group)
            and current_tokens + item_tokens > target_tokens
            and remaining_items >= remaining_groups
            and len(groups) < group_count - 1
        )
        if should_close:
            groups.append(current_group)
            current_group = []
            current_tokens = 0

        current_group.append(subject_id)
        current_tokens += item_tokens

    if current_group:
        groups.append(current_group)
    return groups


def _group_neighbors(*, grouped_ids: list[list[str]], file_edges: list[GroupFileEdge]) -> dict[str, set[str]]:
    subject_to_group: dict[str, str] = {}
    for index, member_ids in enumerate(grouped_ids, start=1):
        group_key = f"segment_{index:03d}"
        for subject_id in member_ids:
            subject_to_group[subject_id] = group_key

    neighbors: dict[str, set[str]] = {f"segment_{index:03d}": set() for index in range(1, len(grouped_ids) + 1)}
    for edge in file_edges:
        left = subject_to_group.get(edge.from_subject_id)
        right = subject_to_group.get(edge.to_subject_id)
        if left is None or right is None or left == right:
            continue
        neighbors[left].add(right)
        neighbors[right].add(left)
    return neighbors


def _internal_degrees(*, member_ids: set[str], file_edges: list[GroupFileEdge]) -> dict[str, int]:
    degree = {subject_id: 0 for subject_id in member_ids}
    for edge in file_edges:
        if edge.from_subject_id in member_ids and edge.to_subject_id in member_ids:
            degree[edge.from_subject_id] += 1
            degree[edge.to_subject_id] += 1
    return degree


def _entrypoint_score(subject_path: str) -> int:
    tokens = set(_tokenize(subject_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]))
    return 1 if tokens & ENTRYPOINT_TOKENS else 0


def _summary_richness(node: GroupFileNode) -> int:
    score = len((node.overall_summary or "").strip())
    if node.group_function:
        score += len(node.group_function.strip())
    score += sum(len(item.strip()) for item in node.important_relationships)
    return score


def _select_representatives(
    *,
    member_ids: list[str],
    node_by_id: dict[str, GroupFileNode],
    internal_degree: dict[str, int],
    representative_count: int,
) -> list[str]:
    ranked = sorted(
        member_ids,
        key=lambda subject_id: (
            -_entrypoint_score(node_by_id[subject_id].subject_path),
            -internal_degree.get(subject_id, 0),
            -_summary_richness(node_by_id[subject_id]),
            node_by_id[subject_id].subject_path,
        ),
    )
    return ranked[:representative_count]


def _rank_members(
    *,
    member_ids: list[str],
    node_by_id: dict[str, GroupFileNode],
    internal_degree: dict[str, int],
    representative_set: set[str],
) -> list[GroupMember]:
    ranked_ids = sorted(
        member_ids,
        key=lambda subject_id: (
            subject_id not in representative_set,
            -_entrypoint_score(node_by_id[subject_id].subject_path),
            -internal_degree.get(subject_id, 0),
            -_summary_richness(node_by_id[subject_id]),
            node_by_id[subject_id].subject_path,
        ),
    )
    members: list[GroupMember] = []
    for rank, subject_id in enumerate(ranked_ids, start=1):
        members.append(
            GroupMember(
                subject_id=subject_id,
                rank=rank,
                is_representative=subject_id in representative_set,
                membership_reason="repo_manager_balanced_dependency_segment",
            )
        )
    return members


def _infer_layer_hint(member_paths: list[str]) -> str:
    if not member_paths:
        return "mixed"
    counter: Counter[str] = Counter()
    for path in member_paths:
        normalized = path.replace("\\", "/")
        prefix = normalized.split("/", 1)[0].lower() if "/" in normalized else "__root__"
        counter[LAYER_HINTS.get(prefix, "mixed")] += 1
    return counter.most_common(1)[0][0]


def _is_infrastructure_seed(member_paths: list[str]) -> bool:
    tokens: set[str] = set()
    for path in member_paths:
        tokens.update(_tokenize(path))
    return bool(tokens & INFRA_TOKENS)


def _tokenize(value: str) -> list[str]:
    lowered = value.lower().replace("/", " ")
    return [token for token in TOKEN_SPLIT_RE.split(lowered) if token]