import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status

from app.config import settings
from app.db import db
from app.logger import logger
from app.rag.pipeline import index_paper
from app.rag.vector_store import get_vector_store
from app.schemas import Message, Paper

router = APIRouter(prefix="/papers", tags=["Papers"])


def run_indexing(paper_id: str, file_path: Path) -> None:
    """Background task: run the indexing pipeline and record the outcome."""
    db.update_paper(paper_id, status="indexing", error_message=None)
    try:
        document, chunk_count = index_paper(paper_id, file_path)
        db.update_paper(
            paper_id,
            title=document.title[:300],
            authors=document.authors,
            abstract=document.abstract,
            page_count=document.page_count,
            chunk_count=chunk_count,
            status="completed",
        )
        db.log_activity("indexed", f"Indexed {document.title[:80]} ({chunk_count} chunks)", paper_id)
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


@router.get("/", response_model=list[Paper])
def list_papers():
    return db.list_papers()


@router.get("/{paper_id}", response_model=Paper)
def get_paper(paper_id: str):
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found.")
    return paper


@router.post("/{paper_id}/reindex", response_model=Paper)
def reindex_paper(paper_id: str, background_tasks: BackgroundTasks):
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found.")
    background_tasks.add_task(run_indexing, paper_id, Path(paper["file_path"]))
    db.update_paper(paper_id, status="uploaded")
    return db.get_paper(paper_id)


@router.delete("/{paper_id}", response_model=Message)
def delete_paper(paper_id: str):
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found.")
    get_vector_store().delete_paper(paper_id)
    Path(paper["file_path"]).unlink(missing_ok=True)
    db.delete_paper(paper_id)
    return Message(message=f"Deleted {paper['title']}.")
