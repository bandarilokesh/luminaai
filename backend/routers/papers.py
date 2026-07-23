import uuid
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, status
from typing import List, Optional
from config.settings import settings
from database.db_helper import db
from backend.schemas import PaperResponse, SimpleMessageResponse, SearchHistoryResponse
from utils.logger import logger

from rag.pdf_processor import extract_pdf_data
from rag.chunker import hierarchical_chunker
from rag.vector_store import index_paper_chunks, delete_paper_from_vector_store
from knowledge.knowledge_extractor import extract_structured_knowledge

router = APIRouter(prefix="/papers", tags=["Papers"])

def run_indexing_pipeline(paper_id: str, file_path: Path):
    """Background task to run text extraction, chunking, and vector indexing."""
    try:
        logger.info(f"Starting indexing pipeline for paper: {paper_id}")
        db.update_paper_status(paper_id, "indexing")
        
        # 1. Extract metadata and text
        metadata, full_text = extract_pdf_data(file_path)
        
        # Update metadata in DB
        db.update_paper_metadata(
            paper_id=paper_id,
            title=metadata.get("title", file_path.stem.replace("_", " ").title()),
            authors=metadata.get("authors", "Unknown"),
            abstract=metadata.get("abstract", ""),
            keywords=metadata.get("keywords", ""),
            doi=metadata.get("doi", ""),
            pub_year=metadata.get("publication_year")
        )
        
        # 2. Chunking
        paper_record = db.get_paper(paper_id)
        paper_name = paper_record["title"] if paper_record else file_path.name
        chunks = hierarchical_chunker.chunk_document(full_text, paper_id, metadata)
        
        # 3. Vector indexing
        index_success = index_paper_chunks(paper_id, chunks)
        if not index_success:
            raise Exception("Failed to index chunks in the vector database.")
        
        # 4. Extract structured knowledge for Knowledge Graph
        try:
            logger.info(f"Extracting structured knowledge for paper: {paper_id}")
            extract_structured_knowledge(paper_id, full_text)
            logger.info(f"Structured knowledge extracted for paper: {paper_id}")
        except Exception as ke:
            logger.warning(f"Knowledge extraction failed for {paper_id} (non-fatal): {ke}")
            
        db.update_paper_status(paper_id, "completed")
        logger.info(f"Indexing pipeline completed successfully for paper: {paper_id}")
        
    except Exception as e:
        error_msg = f"Indexing failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        db.update_paper_status(paper_id, "failed", error_message=error_msg)

@router.post("/upload", response_model=PaperResponse, status_code=status.HTTP_201_CREATED)
async def upload_paper(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload a research paper PDF and trigger background indexing."""
    # Validate extension
    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format. Only PDF files are allowed. Got '.{file_ext}'"
        )
        
    # Save the file to UPLOAD_DIR
    paper_id = str(uuid.uuid4())
    filename = f"{paper_id}.pdf"
    file_path = settings.UPLOAD_DIR / filename
    
    try:
        # Check upload size limit
        # Read a chunk first to check size
        chunk_size = 1024 * 1024  # 1MB chunks
        size_bytes = 0
        
        # Ensure upload dir exists
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(chunk_size):
                size_bytes += len(chunk)
                if size_bytes > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum upload size of {settings.MAX_UPLOAD_SIZE_MB}MB."
                    )
                buffer.write(chunk)
                
    except HTTPException:
        # Clean up partial file on size check violation
        if file_path.exists():
            file_path.unlink()
        raise
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        logger.error(f"Failed to save uploaded file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save file: {str(e)}"
        )
        
    # Insert initial database record
    paper_meta = {
        "id": paper_id,
        "title": file.filename,  # Temp title is the original filename
        "authors": "Extracting...",
        "abstract": "Extracting...",
        "keywords": "",
        "doi": "",
        "publication_year": None,
        "file_path": str(file_path),
        "file_size": size_bytes,
        "status": "uploaded"
    }
    
    db.add_paper(paper_meta)
    
    # Trigger indexing task in background
    background_tasks.add_task(run_indexing_pipeline, paper_id, file_path)
    
    # Return database record
    result = db.get_paper(paper_id)
    if not result:
         raise HTTPException(status_code=404, detail="Paper failed to initialize in DB")
         
    return PaperResponse(**result)

@router.get("/", response_model=List[PaperResponse])
async def list_papers():
    """Retrieve all research papers in the library."""
    try:
        papers = db.list_papers()
        return [PaperResponse(**p) for p in papers]
    except Exception as e:
        logger.error(f"Failed to list papers: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving papers library."
        )

@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: str):
    """Retrieve metadata of a single research paper."""
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found."
        )
    return PaperResponse(**paper)

@router.delete("/{paper_id}", response_model=SimpleMessageResponse)
async def delete_paper(paper_id: str):
    """Delete a research paper from the database, storage, and vector store index."""
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found."
        )
        
    # 1. Delete physical PDF file
    file_path = Path(paper["file_path"])
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {str(e)}")
            
    # 2. Delete vectors from Vector DB
    delete_paper_from_vector_store(paper_id)
    
    # 3. Delete SQLite DB record (cascades automatically to summaries_cache and logs)
    success = db.delete_paper(paper_id)
    
    if success:
        return SimpleMessageResponse(message=f"Paper {paper_id} deleted successfully.", success=True)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete paper records from database."
        )

@router.get("/search/history", response_model=List[SearchHistoryResponse])
async def get_search_history(limit: int = 20):
    """Get recent search queries."""
    history = db.get_search_history(limit)
    return [SearchHistoryResponse(**h) for h in history]

@router.delete("/search/history", response_model=SimpleMessageResponse)
async def clear_search_history():
    """Clear all search query logs."""
    db.clear_search_history()
    return SimpleMessageResponse(message="Search history cleared.", success=True)
