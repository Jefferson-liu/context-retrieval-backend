from services.repo_knowledge.chunking_service import RepoChunkingService


def test_chunking_service_splits_large_content() -> None:
    service = RepoChunkingService(chunk_size=80, chunk_overlap=10)
    text = "\n".join([f"line {idx}" for idx in range(80)])
    chunks = service.chunk_text(text=text, extension=".py")

    assert len(chunks) > 1
    assert all(chunk for chunk in chunks)
