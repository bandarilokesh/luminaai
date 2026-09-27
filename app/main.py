from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth import COOKIE_NAME, LOGIN_PAGE_HTML, OPEN_PATHS, check_code, is_authorized, session_token
from app.config import settings
from app.logger import logger
from app.observability import langfuse
from app.routers import papers, rag

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} | LLM: {settings.LLM_PROVIDER}/{settings.llm_model} | Qdrant: {settings.QDRANT_URL}")
    try:
        from app.rag.vector_store import get_vector_store
        get_vector_store().ensure_collection()
    except Exception as e:
        logger.warning(f"Qdrant is not reachable yet ({e}). Start it with: docker compose up -d qdrant")
    yield
    langfuse.flush()
    logger.info("Shutting down")


app = FastAPI(title=settings.APP_NAME, version="2.0.0", lifespan=lifespan)


@app.middleware("http")
async def access_gate(request: Request, call_next):
    path = request.url.path
    if is_authorized(request) or path.startswith(OPEN_PATHS):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "Access code required."})
    return HTMLResponse(LOGIN_PAGE_HTML, status_code=401)


@app.post("/api/auth/login", include_in_schema=False)
def login(payload: dict = Body(...)):
    if not check_code(str(payload.get("code", ""))):
        return JSONResponse(status_code=401, content={"detail": "Incorrect access code."})
    response = JSONResponse({"status": "ok"})
    response.set_cookie(COOKIE_NAME, session_token(), max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax")
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": f"Unexpected error: {exc}"})


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "service": settings.APP_NAME}


app.include_router(papers.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    return FileResponse(FRONTEND_DIR / "index.html")
