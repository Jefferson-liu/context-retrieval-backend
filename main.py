from __future__ import annotations

from fastapi import FastAPI

from infrastructure.database import init_db

app = FastAPI(
    title="Graphiti POC API",
    version="0.1.0",
    description="Minimal FastAPI setup to explore Graphiti-backed knowledge graph.",
)


@app.get("/health", summary="Health check")
async def health():
    """Basic liveness probe."""
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup():
    await init_db()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
