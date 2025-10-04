import os

import pytest

from scripts.milvus_smoke_test import run_smoke_test

RUN_MILVUS_SMOKE = os.getenv("RUN_MILVUS_SMOKE_TESTS") == "1"


@pytest.mark.skipif(not RUN_MILVUS_SMOKE, reason="Milvus smoke test disabled by default")
@pytest.mark.anyio
async def test_milvus_end_to_end_smoke():
    result = await run_smoke_test()
    assert result.sources, "Expected at least one source from the smoke test query"
    assert result.response_text, "Smoke test response text should not be empty"
