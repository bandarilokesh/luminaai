import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.config import settings
from app.db import db
from app.logger import logger
from app.rag.pipeline import index_paper
from app.rag.vector_store import get_vector_store
from app.schemas import Message, Paper, UploadUrlRequest
import httpx

router = APIRouter(prefix="/papers", tags=["Papers"])
_indexing_lock = threading.Lock()


def _resolve_file_path(paper_id: str, raw_path: Path | str | None = None) -> Path:
    """Resolve file path across local Windows, Docker Linux and relative locations."""
    # First priority: check paper_id.pdf in current UPLOAD_DIR
    candidate_id = settings.UPLOAD_DIR / f"{paper_id}.pdf"
    if candidate_id.is_file():
        return candidate_id

    # Second priority: direct raw path if valid on this filesystem
    if raw_path:
        p = Path(raw_path)
        if p.is_file():
            return p
        # Check by filename extracted across OS path separators
        filename = str(raw_path).replace("\\", "/").split("/")[-1]
        if filename:
            candidate_fn = settings.UPLOAD_DIR / filename
            if candidate_fn.is_file():
                return candidate_fn

    return candidate_id


def run_indexing(paper_id: str, file_path: Path) -> None:
    """Background task: run the indexing pipeline and record the outcome."""
    resolved_path = _resolve_file_path(paper_id, file_path)
    db.update_paper(paper_id, status="indexing", error_message=None)
    with _indexing_lock:
        try:
            document, chunk_count = index_paper(paper_id, resolved_path)
            db.replace_paper_tables(paper_id, document.tables)
            db.delete_audit(paper_id)  # the paper content may have changed; re-audit on demand
            db.update_paper(
                paper_id,
                title=document.title[:300],
                authors=document.authors,
                abstract=document.abstract,
                page_count=document.page_count,
                chunk_count=chunk_count,
                status="completed",
                error_message=None,
            )
            tables = f", {len(document.tables)} tables" if document.tables else ""
            db.log_activity("indexed", f"Indexed {document.title[:80]} ({chunk_count} chunks{tables})", paper_id)
        except Exception as e:
            logger.error(f"Indexing failed for {paper_id}: {e}", exc_info=True)
            db.update_paper(paper_id, status="failed", error_message=str(e)[:500])


@router.post("/upload", response_model=Paper, status_code=status.HTTP_201_CREATED)
async def upload_paper(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only PDF files are supported.")

    paper_id = str(uuid.uuid4())
    file_path = settings.UPLOAD_DIR / f"{paper_id}.pdf"
    limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    size = 0
    try:
        with open(file_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB."
                    )
                out.write(chunk)
    except BaseException:
        file_path.unlink(missing_ok=True)
        raise

    paper = db.add_paper(paper_id, file.filename, file_path, size)
    background_tasks.add_task(run_indexing, paper_id, file_path)
    return paper


@router.post("/upload-url", response_model=Paper, status_code=status.HTTP_201_CREATED)
async def upload_url(request: UploadUrlRequest, background_tasks: BackgroundTasks):
    paper_id = str(uuid.uuid4())
    file_path = settings.UPLOAD_DIR / f"{paper_id}.pdf"
    limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    size = 0
    
    filename = request.filename or request.url.split("/")[-1].split("?")[0]
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
        
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            async with client.stream("GET", request.url) as response:
                response.raise_for_status()
                with open(file_path, "wb") as out:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        size += len(chunk)
                        if size > limit:
                            raise HTTPException(
                                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB."
                            )
                        out.write(chunk)
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Failed to download PDF: {str(e)}")

    paper = db.add_paper(paper_id, filename, file_path, size)
    background_tasks.add_task(run_indexing, paper_id, file_path)
    return paper


@router.get("/", response_model=list[Paper])
def list_papers():
    return db.list_papers()


@router.get("/{paper_id}", response_model=Paper)
def get_paper(paper_id: str):
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found.")
    return paper


@router.get("/{paper_id}/pdf", include_in_schema=False)
def paper_pdf(paper_id: str):
    """Serve the original PDF inline so citations can deep-link to a page (…/pdf#page=N)."""
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found.")
    file_path = _resolve_file_path(paper_id, paper.get("file_path"))
    if not file_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF file not found on disk.")
    return FileResponse(file_path, media_type="application/pdf", content_disposition_type="inline", filename=paper["file_name"])


@router.post("/{paper_id}/reindex", response_model=Paper)
def reindex_paper(paper_id: str, background_tasks: BackgroundTasks):
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found.")
    file_path = _resolve_file_path(paper_id, paper.get("file_path"))
    if not file_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"File {file_path.name} not found on disk.")
    background_tasks.add_task(run_indexing, paper_id, file_path)
    db.update_paper(paper_id, status="uploaded")
    return db.get_paper(paper_id)


@router.delete("/{paper_id}", response_model=Message)
def delete_paper(paper_id: str):
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found.")
    get_vector_store().delete_paper(paper_id)
    file_path = _resolve_file_path(paper_id, paper.get("file_path"))
    file_path.unlink(missing_ok=True)
    db.delete_paper(paper_id)
    return Message(message=f"Deleted {paper['title']}.")
