import sys
import asyncio
from pathlib import Path

import pygit2
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.version_control.git_service import GitService
from services.file.document_file_service import DocumentFileService


def test_git_service_commits_new_document(tmp_path: Path):
    async def workflow() -> None:
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        pygit2.init_repository(str(repo_path), False)

        document_service = DocumentFileService(repo_path=str(repo_path))
        git_service = GitService(repo_path=str(repo_path))

        file_path = await document_service.write_document(1, "sample.txt", "hello world")
        assert file_path is not None
        assert file_path.exists()

        committed = await git_service.commit_changes(
            message="Add sample document",
            added_paths=[file_path],
        )

        assert committed

        repo = pygit2.Repository(str(repo_path))
        head_commit = repo.revparse_single("HEAD")
        assert head_commit.message == "Add sample document"
        tree = head_commit.tree
        entries = [entry.name for entry in tree]
        assert "documents" in entries

        documents_tree = repo[tree["documents"].id]
        document_files = [entry.name for entry in documents_tree]
        assert "1_sample.txt" in document_files

    asyncio.run(workflow())


def test_git_service_commits_updates_and_deletes(tmp_path: Path):
    async def workflow() -> None:
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        pygit2.init_repository(str(repo_path), False)

        document_service = DocumentFileService(repo_path=str(repo_path))
        git_service = GitService(repo_path=str(repo_path))

        file_path = await document_service.write_document(1, "sample.txt", "hello world")
        await git_service.commit_changes("Add sample document", added_paths=[file_path])

        await document_service.write_document(1, "sample.txt", "hello world updated")
        updated = await git_service.commit_changes(
            "Update sample document",
            added_paths=[file_path],
        )
        assert updated

        repo = pygit2.Repository(str(repo_path))
        head_commit = repo.revparse_single("HEAD")
        assert head_commit.message == "Update sample document"

        await document_service.delete_document(1, "sample.txt")
        removed = await git_service.commit_changes(
            "Delete sample document",
            removed_paths=[file_path],
        )
        assert removed

        repo = pygit2.Repository(str(repo_path))
        head_commit = repo.revparse_single("HEAD")
        assert head_commit.message == "Delete sample document"
        tree = head_commit.tree
        entry_names = [entry.name for entry in tree]
        assert "documents" not in entry_names

    asyncio.run(workflow())
