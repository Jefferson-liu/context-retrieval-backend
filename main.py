from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# Import database setup
from infrastructure.database.database import create_tables

# Import routers
from routers.upload import router as upload_router
from routers.search import router as search_router

# Create FastAPI app
app = FastAPI(
    title="Context Retrieval POC Backend",
    description="API for document upload, chunking, embedding, and search",
    version="1.0.0"
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
app.include_router(upload_router, prefix="/api/v1", tags=["Upload"])
app.include_router(search_router, prefix="/api/v1", tags=["Search"])

# Startup event: Create DB tables
@app.on_event("startup")
async def startup_event():
    create_tables()
    print("Database tables created/verified.")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Run app
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)