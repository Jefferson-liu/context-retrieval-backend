from services.repo_knowledge.ingestion_service import _dedupe_edge_rows


def test_dedupe_edge_rows_removes_duplicate_identity_keys() -> None:
    edge_rows = [
        {
            "run_id": "run-1",
            "from_subject_id": "from-a",
            "to_subject_id": "to-a",
            "edge_type": "imports",
            "line": 8,
            "column": 1,
            "evidence": "from infrastructure.models import ChunkRecord, DataRecord",
            "is_external_target": False,
        },
        {
            "run_id": "run-1",
            "from_subject_id": "from-a",
            "to_subject_id": "to-a",
            "edge_type": "imports",
            "line": 8,
            "column": 1,
            "evidence": "from infrastructure.models import ChunkRecord, DataRecord",
            "is_external_target": False,
        },
        {
            "run_id": "run-1",
            "from_subject_id": "from-a",
            "to_subject_id": "to-b",
            "edge_type": "imports",
            "line": 8,
            "column": 1,
            "evidence": "from infrastructure.models import ChunkRecord, DataRecord",
            "is_external_target": False,
        },
    ]

    deduped = _dedupe_edge_rows(edge_rows)

    assert len(deduped) == 2
    assert deduped[0]["to_subject_id"] == "to-a"
    assert deduped[1]["to_subject_id"] == "to-b"
