from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
import json
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from infrastructure.database import init_db
from routers.document_router import router as document_router
from routers.thread_router import router as thread_router
from routers.data_router import router as data_router
from routers.repo_knowledge_router import router as repo_knowledge_router
from routers.repo_knowledge_file_summary_router import router as repo_knowledge_file_summary_router
from routers.repo_knowledge_repo_full_summary_router import router as repo_knowledge_repo_full_summary_router
from routers.repo_knowledge_embedding_router import router as repo_knowledge_embedding_router
from routers.repo_knowledge_repo_manager_router import router as repo_knowledge_repo_manager_router
from routers.repo_knowledge_pipeline_router import router as repo_knowledge_pipeline_router
from services.repo_knowledge.background_runner import get_repo_ingestion_runner
from services.repo_knowledge.file_summary_background_runner import get_repo_file_summary_runner
from services.repo_knowledge.repo_full_summary_background_runner import get_repo_full_summary_runner
from services.repo_knowledge.embedding_background_runner import get_repo_embedding_runner
from services.repo_knowledge.repo_manager_background_runner import get_repo_manager_runner
from services.repo_knowledge.pipeline_background_runner import get_repo_pipeline_runner
from services.repo_knowledge.path_input_normalization import repair_repo_run_json_windows_paths

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    ingestion_runner = get_repo_ingestion_runner()
    file_summary_runner = get_repo_file_summary_runner()
    repo_full_summary_runner = get_repo_full_summary_runner()
    embedding_runner = get_repo_embedding_runner()
    repo_manager_runner = get_repo_manager_runner()
    pipeline_runner = get_repo_pipeline_runner()
    await ingestion_runner.start()
    await file_summary_runner.start()
    await repo_full_summary_runner.start()
    await embedding_runner.start()
    await repo_manager_runner.start()
    await pipeline_runner.start()
    yield
    await pipeline_runner.stop()
    await repo_manager_runner.stop()
    await embedding_runner.stop()
    await repo_full_summary_runner.stop()
    await file_summary_runner.stop()
    await ingestion_runner.stop()


app = FastAPI(
    title="Context Retrieval API",
    version="0.1.0",
    description="FastAPI backend for context retrieval and repo knowledge.",
    lifespan=lifespan,
)


@app.middleware("http")
async def repair_repo_run_windows_path_json(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Repair invalid JSON escapes for pasted Windows paths in repo run creation payloads."""

    if request.method == "POST" and request.url.path in {
        "/repo-knowledge/runs",
        "/repo-knowledge/pipeline-runs",
    }:
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            body = await request.body()
            if body:
                try:
                    body_text = body.decode("utf-8")
                except UnicodeDecodeError:
                    body_text = ""

                if body_text:
                    try:
                        json.loads(body_text)
                    except json.JSONDecodeError as exc:
                        if "Invalid \\escape" in str(exc):
                            repaired_text = repair_repo_run_json_windows_paths(body_text)
                            try:
                                json.loads(repaired_text)
                            except json.JSONDecodeError:
                                logger.warning(
                                    "Repo run payload auto-repair failed path=%s error=%s",
                                    request.url.path,
                                    exc,
                                )
                            else:
                                repaired_body = repaired_text.encode("utf-8")
                                consumed = False

                                async def receive():
                                    nonlocal consumed
                                    if consumed:
                                        return {"type": "http.request", "body": b"", "more_body": False}
                                    consumed = True
                                    return {
                                        "type": "http.request",
                                        "body": repaired_body,
                                        "more_body": False,
                                    }

                                request = Request(request.scope, receive)
                                logger.info(
                                    "Auto-repaired Windows path escapes for repo run payload path=%s",
                                    request.url.path,
                                )
    return await call_next(request)


@app.exception_handler(StarletteHTTPException)
async def log_http_exception(request: Request, exc: StarletteHTTPException):
    """Log handled HTTP errors and preserve FastAPI-style error payloads."""
    logger.warning(
        "HTTPException method=%s path=%s status=%s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def log_request_validation_error(request: Request, exc: RequestValidationError):
    """Log request validation failures with full details."""
    serialized_errors = _serialize_validation_errors(exc.errors())
    logger.warning(
        "RequestValidationError method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        serialized_errors,
    )
    return JSONResponse(
        status_code=422,
        content={"detail": serialized_errors},
    )


@app.exception_handler(Exception)
async def log_unhandled_exception(request: Request, exc: Exception):
    """Log unhandled exceptions before returning a generic 500 response."""
    logger.exception(
        "Unhandled exception method=%s path=%s error=%s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


@app.get("/health", summary="Health check")
async def health():
    """Basic liveness probe."""
    return {"status": "ok"}


app.include_router(document_router)
app.include_router(thread_router)
app.include_router(data_router)
app.include_router(repo_knowledge_router)
app.include_router(repo_knowledge_file_summary_router)
app.include_router(repo_knowledge_repo_full_summary_router)
app.include_router(repo_knowledge_embedding_router)
app.include_router(repo_knowledge_repo_manager_router)
app.include_router(repo_knowledge_pipeline_router)


def _serialize_validation_errors(errors: list[dict]) -> list[dict]:
    """Return JSON-safe validation errors for custom exception responses."""

    serialized: list[dict] = []
    for error in errors:
        item = dict(error)
        ctx = item.get("ctx")
        if isinstance(ctx, dict):
            item["ctx"] = {
                key: (str(value) if isinstance(value, Exception) else value)
                for key, value in ctx.items()
            }
        serialized.append(item)
    return serialized


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
