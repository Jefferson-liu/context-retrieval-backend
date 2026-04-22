from pathlib import Path

from services.repo_knowledge.discovery_service import iter_repo_files


def test_iter_repo_files_respects_extension_and_excludes(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "src" / "ignore.txt").write_text("x", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("x", encoding="utf-8")

    files = list(
        iter_repo_files(
            root_path=tmp_path,
            include_extensions={".py", ".js"},
            excluded_dirs={"node_modules"},
            exclude_globs=["src/ignore.*"],
        )
    )

    assert [item.relative_path for item in files] == ["src/main.py"]


def test_iter_repo_files_excludes_dot_venv_wsl_by_default(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / ".venv-wsl" / "lib").mkdir(parents=True)
    (tmp_path / ".venv-wsl" / "lib" / "ignored.py").write_text("print('ignored')", encoding="utf-8")

    files = list(
        iter_repo_files(
            root_path=tmp_path,
            include_extensions={".py"},
            excluded_dirs=set(),
            exclude_globs=[],
        )
    )

    assert [item.relative_path for item in files] == ["src/main.py"]
