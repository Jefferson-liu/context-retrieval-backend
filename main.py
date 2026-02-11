from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from infrastructure.database import init_db
from infrastructure.graphiti import ensure_bootstrap
from routers.document_router import router as document_router
from routers.thread_router import router as thread_router
from routers.data_router import router as data_router
from routers.search_router import router as search_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await ensure_bootstrap()
    yield


app = FastAPI(
    title="Graphiti POC API",
    version="0.1.0",
    description="Minimal FastAPI setup to explore Graphiti-backed knowledge graph.",
    lifespan=lifespan,
)


@app.get("/health", summary="Health check")
async def health():
    """Basic liveness probe."""
    return {"status": "ok"}


app.include_router(document_router)
app.include_router(thread_router)
app.include_router(data_router)
app.include_router(search_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
