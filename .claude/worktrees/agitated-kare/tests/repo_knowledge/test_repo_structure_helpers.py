from __future__ import annotations

from services.repo_knowledge.mcp_tools_service import _insert_path, _new_dir_node, _render_tree


def test_repo_structure_helpers_build_tree_with_counts() -> None:
    root = _new_dir_node(name="/", path="")
    _insert_path(root=root, path="services/recommendation/rank.py")
    _insert_path(root=root, path="services/recommendation/ingest.py")
    _insert_path(root=root, path="routers/recommendation/routes.py")

    rendered = _render_tree(node=root, depth=0, max_depth=4, include_file_counts=True)

    assert rendered["type"] == "dir"
    assert rendered["file_count"] == 3
    assert [child["name"] for child in rendered["children"]] == ["routers", "services"]


def test_repo_structure_helpers_respect_max_depth() -> None:
    root = _new_dir_node(name="/", path="")
    _insert_path(root=root, path="services/recommendation/rank.py")

    rendered = _render_tree(node=root, depth=0, max_depth=1, include_file_counts=False)
    services = rendered["children"][0]

    assert services["name"] == "services"
    assert services.get("truncated") is True
