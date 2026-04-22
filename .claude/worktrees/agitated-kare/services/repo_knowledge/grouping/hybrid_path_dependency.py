from __future__ import annotations

from collections import Counter, defaultdict
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
INFRA_TOKENS = {"util", "helper", "common", "shared", "base", "config", "test"}
TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


class HybridPathDependencyGrouper(GroupingStrategy):
    """Deterministic grouper using path seeds and dependency-affinity merge."""

    def __init__(
        self,
        *,
        path_depth: int,
        merge_min_affinity: float,
        max_member_files: int,
        representative_count: int,
    ) -> None:
        self.path_depth = max(1, path_depth)
        self.merge_min_affinity = max(0.0, min(merge_min_affinity, 1.0))
        self.max_member_files = max(2, max_member_files)
        self.representative_count = max(1, representative_count)

    def build_groups(self, *, file_nodes: list[GroupFileNode], file_edges: list[GroupFileEdge]) -> GroupBuildResult:
        if not file_nodes:
            return GroupBuildResult(groups=[], members_seen=0)

        node_by_id = {node.subject_id: node for node in file_nodes}
        valid_ids = set(node_by_id)
        filtered_edges = [
            edge for edge in file_edges if edge.from_subject_id in valid_ids and edge.to_subject_id in valid_ids
        ]

        seed_by_subject: dict[str, str] = {}
        subjects_by_seed: dict[str, set[str]] = defaultdict(set)
        for node in sorted(file_nodes, key=lambda item: item.subject_path):
            seed = _seed_key(node.subject_path, self.path_depth)
            seed_by_subject[node.subject_id] = seed
            subjects_by_seed[seed].add(node.subject_id)

        parent = {seed: seed for seed in subjects_by_seed}

        def find(seed: str) -> str:
            root = seed
            while parent[root] != root:
                root = parent[root]
            while parent[seed] != seed:
                nxt = parent[seed]
                parent[seed] = root
                seed = nxt
            return root

        def union(a: str, b: str) -> bool:
            ra = find(a)
            rb = find(b)
            if ra == rb:
                return False
            if ra > rb:
                ra, rb = rb, ra
            parent[rb] = ra
            return True

        # Iteratively merge plausible high-affinity seed clusters.
        while True:
            root_members = _root_members(subjects_by_seed=subjects_by_seed, find=find)
            pair_counts = _cross_edge_counts(
                edges=filtered_edges,
                subject_root={subject_id: find(seed_by_subject[subject_id]) for subject_id in valid_ids},
            )
            candidates: list[tuple[float, int, str, str]] = []
            for (left, right), cross_edges in pair_counts.items():
                left_size = len(root_members.get(left, set()))
                right_size = len(root_members.get(right, set()))
                if left_size == 0 or right_size == 0:
                    continue
                affinity = cross_edges / max(1, min(left_size, right_size))
                if affinity < self.merge_min_affinity:
                    continue
                if left_size + right_size > self.max_member_files:
                    continue
                if not _is_plausible_pair(left, right, cross_edges=cross_edges, left_size=left_size, right_size=right_size):
                    continue
                candidates.append((affinity, cross_edges, left, right))

            if not candidates:
                break

            candidates.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
            merged_any = False
            for _affinity, _edges, left, right in candidates:
                if union(left, right):
                    merged_any = True
            if not merged_any:
                break

        grouped_subjects = _group_subjects_by_root(valid_ids=valid_ids, seed_by_subject=seed_by_subject, find=find)
        neighbor_groups = _group_neighbors(
            grouped_subjects=grouped_subjects,
            edges=filtered_edges,
            subject_to_group={subject_id: group_root for group_root, members in grouped_subjects.items() for subject_id in members},
        )

        groups: list[BuiltGroup] = []
        for root, member_ids in sorted(grouped_subjects.items()):
            members = sorted(member_ids, key=lambda subject_id: node_by_id[subject_id].subject_path)
            if not members:
                continue

            seed_parts = sorted({seed_by_subject[subject_id] for subject_id in members})
            group_key = seed_parts[0] if len(seed_parts) == 1 else "merged:" + "+".join(seed_parts)
            layer_hint = _infer_layer_hint([node_by_id[subject_id].subject_path for subject_id in members])
            infra_seed = _is_infrastructure_seed(group_key=group_key, member_paths=[node_by_id[item].subject_path for item in members])

            internal_degree = _internal_degrees(member_ids=set(members), edges=filtered_edges)
            representatives = _select_representatives(
                member_ids=members,
                node_by_id=node_by_id,
                internal_degree=internal_degree,
                representative_count=self.representative_count,
            )
            representative_set = set(representatives)

            ranked_members = _rank_members(
                member_ids=members,
                node_by_id=node_by_id,
                internal_degree=internal_degree,
                representative_set=representative_set,
            )

            group_id = str(uuid5(NAMESPACE_URL, f"{group_key}|{'|'.join(members)}"))
            groups.append(
                BuiltGroup(
                    group_id=group_id,
                    group_key=group_key,
                    group_label=group_key,
                    layer_hint=layer_hint,
                    member_count=len(members),
                    dependency_neighbor_count=len(neighbor_groups.get(root, set())),
                    is_infrastructure_seed=infra_seed,
                    heuristics={
                        "seed_parts": seed_parts,
                        "merge_strategy": "hybrid_path_dependency",
                        "member_paths": [node_by_id[subject_id].subject_path for subject_id in members],
                    },
                    representative_subject_ids=representatives,
                    members=ranked_members,
                )
            )

        groups.sort(key=lambda item: (item.group_key, item.group_id))
        members_seen = sum(group.member_count for group in groups)
        return GroupBuildResult(groups=groups, members_seen=members_seen)


def _seed_key(subject_path: str, depth: int) -> str:
    normalized = subject_path.replace("\\", "/").strip("/")
    parts = [part for part in normalized.split("/") if part]
    if len(parts) <= 1:
        stem = parts[0].rsplit(".", 1)[0] if parts else "root"
        token = _tokenize(stem)[0] if _tokenize(stem) else "misc"
        return f"__root__/{token}"
    return "/".join(parts[: min(depth, len(parts) - 1)])


def _tokenize(value: str) -> list[str]:
    lowered = value.lower()
    return [token for token in TOKEN_SPLIT_RE.split(lowered) if token]


def _path_tokens(seed: str) -> set[str]:
    return set(_tokenize(seed.replace("/", " ")))


def _is_plausible_pair(left: str, right: str, *, cross_edges: int, left_size: int, right_size: int) -> bool:
    if _path_tokens(left) & _path_tokens(right):
        return True
    heavy_threshold = max(2, min(left_size, right_size) // 2)
    return cross_edges >= heavy_threshold


def _root_members(*, subjects_by_seed: dict[str, set[str]], find) -> dict[str, set[str]]:  # noqa: ANN001
    roots: dict[str, set[str]] = defaultdict(set)
    for seed, members in subjects_by_seed.items():
        roots[find(seed)].update(members)
    return roots


def _cross_edge_counts(*, edges: list[GroupFileEdge], subject_root: dict[str, str]) -> dict[tuple[str, str], int]:
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for edge in edges:
        left = subject_root.get(edge.from_subject_id)
        right = subject_root.get(edge.to_subject_id)
        if left is None or right is None or left == right:
            continue
        pair = (left, right) if left < right else (right, left)
        pair_counts[pair] += 1
    return pair_counts


def _group_subjects_by_root(*, valid_ids: set[str], seed_by_subject: dict[str, str], find) -> dict[str, list[str]]:  # noqa: ANN001
    grouped: dict[str, list[str]] = defaultdict(list)
    for subject_id in sorted(valid_ids):
        grouped[find(seed_by_subject[subject_id])].append(subject_id)
    return grouped


def _group_neighbors(
    *,
    grouped_subjects: dict[str, list[str]],
    edges: list[GroupFileEdge],
    subject_to_group: dict[str, str],
) -> dict[str, set[str]]:
    neighbors: dict[str, set[str]] = {group_id: set() for group_id in grouped_subjects}
    for edge in edges:
        from_group = subject_to_group.get(edge.from_subject_id)
        to_group = subject_to_group.get(edge.to_subject_id)
        if from_group is None or to_group is None or from_group == to_group:
            continue
        neighbors[from_group].add(to_group)
        neighbors[to_group].add(from_group)
    return neighbors


def _infer_layer_hint(member_paths: list[str]) -> str:
    if not member_paths:
        return "mixed"
    counter: Counter[str] = Counter()
    for path in member_paths:
        normalized = path.replace("\\", "/")
        prefix = normalized.split("/", 1)[0].lower() if "/" in normalized else "__root__"
        hint = LAYER_HINTS.get(prefix, "mixed")
        counter[hint] += 1
    return counter.most_common(1)[0][0]


def _is_infrastructure_seed(*, group_key: str, member_paths: list[str]) -> bool:
    tokens = set(_tokenize(group_key))
    for path in member_paths:
        tokens.update(_tokenize(path))
    if not tokens:
        return False
    return bool(tokens & INFRA_TOKENS)


def _internal_degrees(*, member_ids: set[str], edges: list[GroupFileEdge]) -> dict[str, int]:
    degree = {subject_id: 0 for subject_id in member_ids}
    for edge in edges:
        if edge.from_subject_id in member_ids and edge.to_subject_id in member_ids:
            degree[edge.from_subject_id] += 1
            degree[edge.to_subject_id] += 1
    return degree


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
            -internal_degree.get(subject_id, 0),
            -_summary_richness(node_by_id[subject_id]),
            node_by_id[subject_id].subject_path,
        ),
    )
    return ranked[: min(representative_count, len(ranked))]


def _rank_members(
    *,
    member_ids: list[str],
    node_by_id: dict[str, GroupFileNode],
    internal_degree: dict[str, int],
    representative_set: set[str],
) -> list[GroupMember]:
    ordered = sorted(
        member_ids,
        key=lambda subject_id: (
            0 if subject_id in representative_set else 1,
            -internal_degree.get(subject_id, 0),
            -_summary_richness(node_by_id[subject_id]),
            node_by_id[subject_id].subject_path,
        ),
    )
    members: list[GroupMember] = []
    for idx, subject_id in enumerate(ordered, start=1):
        members.append(
            GroupMember(
                subject_id=subject_id,
                rank=idx,
                is_representative=subject_id in representative_set,
                membership_reason="path_seed_and_dependency_affinity",
            )
        )
    return members
