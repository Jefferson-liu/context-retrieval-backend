from __future__ import annotations

from services.repo_knowledge.grouping.hybrid_path_dependency import HybridPathDependencyGrouper
from services.repo_knowledge.grouping.types import GroupFileEdge, GroupFileNode


def _node(subject_id: str, subject_path: str, summary: str) -> GroupFileNode:
    return GroupFileNode(
        subject_id=subject_id,
        subject_path=subject_path,
        language="python",
        overall_summary=summary,
        group_function=None,
        important_relationships=[],
    )


def test_hybrid_grouping_merges_path_related_clusters() -> None:
    nodes = [
        _node("n1", "services/recommendation/ingest.py", "Ingest recommendation events"),
        _node("n2", "services/recommendation/rank.py", "Rank recommendation candidates"),
        _node("n3", "routers/recommendation/routes.py", "Expose recommendation API"),
        _node("n4", "services/billing/charge.py", "Handle payment charge"),
    ]
    edges = [
        GroupFileEdge(from_subject_id="n1", to_subject_id="n2", edge_type="imports"),
        GroupFileEdge(from_subject_id="n3", to_subject_id="n2", edge_type="imports"),
    ]

    grouper = HybridPathDependencyGrouper(
        path_depth=2,
        merge_min_affinity=0.35,
        max_member_files=60,
        representative_count=3,
    )
    result = grouper.build_groups(file_nodes=nodes, file_edges=edges)

    assert len(result.groups) == 2
    grouped_paths = [
        sorted(member.subject_id for member in group.members)
        for group in result.groups
    ]
    assert sorted(grouped_paths) == [["n1", "n2", "n3"], ["n4"]]


def test_hybrid_grouping_is_deterministic() -> None:
    nodes = [
        _node("n1", "services/recommendation/ingest.py", "Ingest recommendation events"),
        _node("n2", "services/recommendation/rank.py", "Rank recommendation candidates"),
        _node("n3", "routers/recommendation/routes.py", "Expose recommendation API"),
    ]
    edges = [
        GroupFileEdge(from_subject_id="n1", to_subject_id="n2", edge_type="imports"),
        GroupFileEdge(from_subject_id="n3", to_subject_id="n2", edge_type="imports"),
    ]

    grouper = HybridPathDependencyGrouper(
        path_depth=2,
        merge_min_affinity=0.35,
        max_member_files=60,
        representative_count=2,
    )

    first = grouper.build_groups(file_nodes=nodes, file_edges=edges)
    second = grouper.build_groups(file_nodes=nodes, file_edges=edges)

    assert [group.group_id for group in first.groups] == [group.group_id for group in second.groups]
    assert [group.group_key for group in first.groups] == [group.group_key for group in second.groups]
    assert [
        [member.subject_id for member in group.members]
        for group in first.groups
    ] == [
        [member.subject_id for member in group.members]
        for group in second.groups
    ]
