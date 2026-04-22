from __future__ import annotations

from services.repo_knowledge.grouping.repo_manager import AdaptiveDependencyRepoManager
from services.repo_knowledge.grouping.types import GroupFileEdge, GroupFileNode


def test_repo_manager_balances_dependency_segments() -> None:
    manager = AdaptiveDependencyRepoManager(max_group_tokens=120, representative_count=2)
    nodes = [
        GroupFileNode(
            subject_id=f"file-{index}",
            subject_path=path,
            language="python",
            overall_summary=("summary " * 20) + path,
            group_function=None,
            important_relationships=[],
        )
        for index, path in enumerate(
            [
                "main.py",
                "routers/api.py",
                "services/use_case.py",
                "infrastructure/repository.py",
            ],
            start=1,
        )
    ]
    edges = [
        GroupFileEdge(from_subject_id="file-1", to_subject_id="file-2", edge_type="imports"),
        GroupFileEdge(from_subject_id="file-2", to_subject_id="file-3", edge_type="imports"),
        GroupFileEdge(from_subject_id="file-3", to_subject_id="file-4", edge_type="imports"),
    ]

    result = manager.build_groups(file_nodes=nodes, file_edges=edges)

    assert len(result.groups) >= 2
    assert result.members_seen == 4
    assert result.groups[0].heuristics["strategy"] == "adaptive_dependency_repo_manager"
    assert result.groups[0].members[0].membership_reason == "repo_manager_balanced_dependency_segment"


def test_repo_manager_prefers_entrypoint_first() -> None:
    manager = AdaptiveDependencyRepoManager(max_group_tokens=9999, representative_count=1)
    nodes = [
        GroupFileNode(
            subject_id="a",
            subject_path="pkg/worker.py",
            language="python",
            overall_summary="worker summary",
            group_function=None,
            important_relationships=[],
        ),
        GroupFileNode(
            subject_id="b",
            subject_path="main.py",
            language="python",
            overall_summary="entry summary",
            group_function=None,
            important_relationships=[],
        ),
    ]

    result = manager.build_groups(file_nodes=nodes, file_edges=[])

    assert result.groups[0].members[0].subject_id == "b"