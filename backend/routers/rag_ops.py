import time
import os
import psutil
from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
from pathlib import Path
from config.settings import settings
from database.db_helper import db
from backend.schemas import (
    SystemStatusResponse, QARequest, QAResponse,
    SummaryRequest, SummaryResponse,
    QuizRequest, QuizResponse,
    FlashcardRequest, FlashcardResponse,
    ResearchGapResponse,
    DashboardStatsResponse, ActivityItem, ActivityResponse
)
from utils.logger import logger

# Import models/rag service endpoints (stubs for now)
from services.gemini_client import gemini_client
from rag.qa_service import answer_question
from rag.summarizer import generate_paper_summary
from rag.extractions import generate_quiz, generate_flashcards, detect_research_gaps

import torch

router = APIRouter(tags=["RAG Operations"])

@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status():
    """Retrieve detailed local system and model status configurations."""
    try:
        gpu_available = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if gpu_available else None
        
        provider_status = "Connected" if gemini_client.is_configured() else "Not Configured"
        current_model = settings.MODEL_NAME
        
        papers_count = len(db.list_papers())
        
        db_size = 0
        if settings.DATABASE_PATH.exists():
            db_size = settings.DATABASE_PATH.stat().st_size
            
        return SystemStatusResponse(
            app_name=settings.APP_NAME,
            debug=settings.DEBUG,
            gpu_available=gpu_available,
            gpu_device_name=gpu_name,
            provider_status=provider_status,
            current_model=current_model,
            total_papers=papers_count,
            db_size_bytes=db_size
        )
    except Exception as e:
        logger.error(f"Error fetching system status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve status info: {str(e)}"
        )

@router.post("/qa", response_model=QAResponse)
async def ask_question_endpoint(req: QARequest):
    """Ask a question about a single paper or multiple papers."""
    try:
        start_time = time.time()
        
        # Log the search query in search history
        db.add_search_history(req.question)
        
        # Determine LLM model to use
        llm_model = req.llm_model or settings.MODEL_NAME
        
        # Answer question
        qa_result = answer_question(
            paper_ids=req.paper_ids,
            question=req.question,
            model_name=llm_model,
            use_hybrid=req.use_hybrid,
            use_reranker=req.use_reranker
        )
        
        latency = time.time() - start_time
        qa_result["latency_sec"] = latency
        
        # Log QA interaction in DB
        # If answering for a specific single paper, bind it
        p_id = req.paper_ids[0] if len(req.paper_ids) == 1 else None
        db.add_qa_log(
            paper_id=p_id,
            question=req.question,
            answer=qa_result["answer"],
            citations=qa_result["citations"],
            confidence_score=qa_result["confidence_score"]
        )
        
        return QAResponse(**qa_result)
        
    except Exception as e:
        logger.error(f"Error in QA: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing QA request: {str(e)}"
        )

@router.post("/summary", response_model=SummaryResponse)
async def generate_summary_endpoint(req: SummaryRequest):
    """Generate a summary of a paper, using cache if available."""
    try:
        start_time = time.time()
        
        # Validate paper exists
        paper = db.get_paper(req.paper_id)
        if not paper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Paper with ID {req.paper_id} not found."
            )
            
        # Check SQLite summaries cache
        cached_summary = db.get_summary_cache(req.paper_id, req.summary_type)
        if cached_summary:
            latency = time.time() - start_time
            logger.info(f"Summary Cache HIT for paper {req.paper_id} - type: {req.summary_type}")
            return SummaryResponse(
                paper_id=req.paper_id,
                summary_type=req.summary_type,
                summary_text=cached_summary,
                latency_sec=latency
            )
            
        # Cache Miss: Generate summary
        llm_model = req.llm_model or settings.MODEL_NAME
        summary_text = generate_paper_summary(req.paper_id, req.summary_type, llm_model)
        
        # Store in cache
        db.add_summary_cache(req.paper_id, req.summary_type, summary_text)
        
        latency = time.time() - start_time
        return SummaryResponse(
            paper_id=req.paper_id,
            summary_type=req.summary_type,
            summary_text=summary_text,
            latency_sec=latency
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Summarization: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating summary: {str(e)}"
        )

@router.post("/quiz", response_model=QuizResponse)
async def generate_quiz_endpoint(req: QuizRequest):
    """Generate a learning quiz over selected papers."""
    try:
        start_time = time.time()
        questions = generate_quiz(req.paper_ids, req.quiz_type, req.difficulty, req.num_questions)
        latency = time.time() - start_time
        
        return QuizResponse(
            quiz_type=req.quiz_type,
            difficulty=req.difficulty,
            questions=questions,
            latency_sec=latency
        )
    except Exception as e:
        logger.error(f"Error in Quiz generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating quiz: {str(e)}"
        )

@router.post("/flashcards", response_model=FlashcardResponse)
async def generate_flashcards_endpoint(req: FlashcardRequest):
    """Generate flashcards from selected research papers."""
    try:
        start_time = time.time()
        cards = generate_flashcards(req.paper_ids, req.num_cards)
        latency = time.time() - start_time
        
        return FlashcardResponse(
            cards=cards,
            latency_sec=latency
        )
    except Exception as e:
        logger.error(f"Error in Flashcards generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating flashcards: {str(e)}"
        )

@router.post("/gap-detector", response_model=ResearchGapResponse)
async def gap_detector_endpoint(paper_ids: List[str]):
    """Identify research limitations, future works, and novel opportunities across papers."""
    try:
        start_time = time.time()
        gaps = detect_research_gaps(paper_ids)
        latency = time.time() - start_time
        
        return ResearchGapResponse(
            gaps=gaps,
            latency_sec=latency
        )
    except Exception as e:
        logger.error(f"Error in Research Gap detection: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error detecting research gaps: {str(e)}"
        )

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats():
    """Get aggregated dashboard statistics."""
    try:
        stats = db.get_dashboard_stats()
        return DashboardStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching stats: {str(e)}"
        )

@router.get("/activity", response_model=ActivityResponse)
async def get_recent_activity(limit: int = 10):
    """Get recent activity timeline for dashboard."""
    try:
        activities = db.get_recent_activity(limit)
        items = [ActivityItem(**a) for a in activities]
        return ActivityResponse(activities=items)
    except Exception as e:
        logger.error(f"Error fetching activity: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching activity: {str(e)}"
        )

