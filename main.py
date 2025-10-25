from fastapi import FastAPI, Depends
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
from routers.knowledge_router import router as knowledge_router
from routers.user_router import router as user_router
from routers.dependencies import require_api_key
from config import settings

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
docs_url = None if settings.API_AUTH_TOKEN else "/docs"
redoc_url = None if settings.API_AUTH_TOKEN else "/redoc"
openapi_url = None if settings.API_AUTH_TOKEN else "/openapi.json"

app = FastAPI(
    title="Context Retrieval POC Backend",
    description="API for document upload, chunking, embedding, and search",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
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
app.include_router(
    document_router,
    prefix="/api",
    tags=["Document"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(
    query_router,
    prefix="/api",
    tags=["Query"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(
    knowledge_router,
    prefix="/api",
    tags=["Knowledge"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(
    user_router,
    prefix="/api",
    tags=["User"],
    dependencies=[Depends(require_api_key)],
)

if settings.API_AUTH_TOKEN:
    from fastapi.openapi.docs import get_swagger_ui_html
    from fastapi.openapi.utils import get_openapi
    from fastapi.responses import JSONResponse

    @app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(require_api_key)])
    async def protected_openapi():
        return JSONResponse(get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
            description=app.description,
        ))

    @app.get("/docs", include_in_schema=False, dependencies=[Depends(require_api_key)])
    async def protected_swagger():
        return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} - Docs")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Run app
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
