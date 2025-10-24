import os
from pathlib import Path

import pytest
import requests


RUN_API_SMOKE = os.getenv("RUN_API_SMOKE_TESTS") == "1"
TESTFILES_DIR = Path(__file__).resolve().parents[1] / "testfiles"


@pytest.mark.skipif(not RUN_API_SMOKE, reason="API smoke tests disabled by default")
def test_upload_endpoint_smoke():
    url = "http://127.0.0.1:8000/api/upload"
    file_path = TESTFILES_DIR / "smoke_test_document.txt"

    with file_path.open("rb") as f:
        files = {"file": (file_path.name, f, "text/plain")}
        try:
            response = requests.post(url, files=files, timeout=5)
        except requests.exceptions.RequestException as exc:  # pragma: no cover - network dependent
            pytest.fail(f"Upload smoke test failed to reach API: {exc}")

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("message") == "Document uploaded and processed successfully"
    assert "doc_id" in payload