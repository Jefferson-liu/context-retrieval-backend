import os

import pytest
import requests


RUN_API_SMOKE = os.getenv("RUN_API_SMOKE_TESTS") == "1"


@pytest.mark.skipif(not RUN_API_SMOKE, reason="API smoke tests disabled by default")
def test_upload_endpoint_smoke():
    url = "http://127.0.0.1:8000/api/upload"
    file_path = "test_utf8.txt"

    with open(file_path, "rb") as f:
        files = {"file": ("test_utf8.txt", f, "text/plain")}
        try:
            response = requests.post(url, files=files, timeout=5)
        except requests.exceptions.RequestException as exc:  # pragma: no cover - network dependent
            pytest.fail(f"Upload smoke test failed to reach API: {exc}")

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("message") == "Document uploaded and processed successfully"
    assert "doc_id" in payload