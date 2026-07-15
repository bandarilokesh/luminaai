import sys
import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from utils.logger import logger
from database.db_helper import db
from backend.routers import papers, rag_ops

# Resolve frontend static directory
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler for FastAPI."""
    logger.info("Starting PaperMind AI Backend API...")
    # Initialize settings directories
    settings.create_directories()
    # Log database details
    logger.info(f"Database loaded at: {settings.DATABASE_PATH}")
    yield
    logger.info("Shutting down PaperMind AI Backend API...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Local RAG Backend API for Research Paper QA and Summarization.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Open for local access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception caught on request {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"An unexpected system error occurred: {str(exc)}"}
    )

# Base health checks
@app.get("/health", tags=["Health"])
async def health_check():
    """Simple service health probe."""
    return {"status": "healthy", "service": settings.APP_NAME}

# Include API routers
app.include_router(papers.router, prefix="/api")
app.include_router(rag_ops.router, prefix="/api")

# Mount static files (CSS, JS, assets) — this must come after API routes
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# SPA catch-all: serve index.html for all non-API, non-static routes
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    """Serve the SPA frontend for any unmatched route."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(
        status_code=404,
        content={"detail": "Frontend not found. Ensure frontend/static/index.html exists."}
    )

if __name__ == "__main__":
    logger.info("Running API server directly via uvicorn...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
