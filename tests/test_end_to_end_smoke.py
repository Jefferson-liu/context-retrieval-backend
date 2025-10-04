import os
import time
from pathlib import Path

import pytest
import requests

API_BASE_URL = os.getenv("SMOKE_TEST_API_URL", "http://127.0.0.1:8000/api")
RUN_E2E_SMOKE = os.getenv("RUN_E2E_SMOKE_TESTS", "0") == "1"


def _wait_for_api(url: str, attempts: int = 5, delay: float = 1.0) -> bool:
    for _ in range(attempts):
        try:
            response = requests.get(url, timeout=3)
        except requests.RequestException:
            time.sleep(delay)
            continue

        if response.status_code == 200:
            return True
        time.sleep(delay)
    return False


@pytest.mark.skipif(not RUN_E2E_SMOKE, reason="End-to-end smoke tests disabled by default")
def test_upload_process_and_query_roundtrip():
    health_url = API_BASE_URL.replace("/api", "/health")
    if not _wait_for_api(health_url):
        pytest.skip(
            "FastAPI service is not reachable at {health_url}; start the API before running the smoke test.".format(
                health_url=health_url
            )
        )

    upload_url = f"{API_BASE_URL}/upload"
    query_url = f"{API_BASE_URL}/query"

    fixture_path = Path(__file__).parent / "fixtures" / "smoke_test_document.txt"
    document_bytes = fixture_path.read_bytes()

    files = {
        "file": (fixture_path.name, document_bytes, "text/plain"),
    }

    upload_response = requests.post(upload_url, files=files, timeout=30)
    assert upload_response.status_code == 200, upload_response.text

    payload = upload_response.json()
    assert payload.get("message") == "Document uploaded and processed successfully"
    doc_id = payload.get("doc_id")
    assert doc_id is not None

    query_response = requests.post(
        query_url,
        params={"query_text": "Vector coffee roasters"},
        timeout=30,
    )
    assert query_response.status_code == 200, query_response.text
    query_payload = query_response.json()

    response_text = query_payload.get("response", "")
    sources = query_payload.get("sources", [])

    assert response_text, "Expected non-empty response"
    assert any("Vector coffee roasters" in src.get("snippet", "") for src in sources), (
        "Expected the smoke test snippet to appear in at least one source"
    )
