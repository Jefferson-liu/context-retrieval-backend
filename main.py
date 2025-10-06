from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from contextlib import asynccontextmanager
from sqlalchemy import text

# Import database setup
from infrastructure.database.database import create_tables
from infrastructure.database.setup import (
    configure_multi_tenant_rls,
    seed_default_tenant_and_project,
)

# Import routers
from routers.document_router import router as document_router
from routers.query_router import router as query_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from infrastructure.database.database import engine
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        print("pgvector extension enabled.")

    await create_tables()

    async with engine.begin() as conn:
        await configure_multi_tenant_rls(conn)

    await seed_default_tenant_and_project()
    print("Database tables created/verified and multi-tenant defaults seeded.")
    yield
    # Shutdown (if needed)

# Create FastAPI app
app = FastAPI(
    title="Context Retrieval POC Backend",
    description="API for document upload, chunking, embedding, and search",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(document_router, prefix="/api", tags=["Document"])
app.include_router(query_router, prefix="/api", tags=["Query"])

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Run app
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)