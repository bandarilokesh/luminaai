import time
import os
import psutil
import json
import asyncio
import numpy as np
from fastapi import APIRouter, HTTPException, status, WebSocket, WebSocketDisconnect, Body
from typing import List, Dict, Any
from pathlib import Path
from config.settings import settings
from database.db_helper import db
from backend.schemas import (
    SystemStatusResponse, QARequest, QAResponse,
    SummaryRequest, SummaryResponse,
    QuizRequest, QuizResponse,
    FlashcardRequest, FlashcardResponse,
    DashboardStatsResponse, ActivityItem, ActivityResponse,
    GraphResponse, CompareResponse, ResearchGapResponse
)
from utils.logger import logger

# Import models/rag service endpoints (stubs for now)
from services.gemini_client import gemini_client
from rag.qa_service import answer_question
from rag.summarizer import generate_paper_summary
from rag.extractions import generate_quiz, generate_flashcards, detect_research_gaps
from models.llm_connector import stream_llm
from rag.retriever import retrieve_context
from models.prompt_templates import build_qa_prompt
from agents.research_agent import ResearchAgent
from knowledge.graph_manager import graph_manager
from knowledge.graph_store import graph_store
from knowledge.knowledge_extractor import extract_structured_knowledge
from rag.pdf_processor import extract_pdf_data

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
            confidence_score=qa_result["confidence_score"],
            faithfulness_score=qa_result.get("faithfulness_score", 0.0),
            verification_json=json.dumps(qa_result.get("verification_json", {}))
        )
        
        return QAResponse(**qa_result)
        
    except Exception as e:
        logger.error(f"Error in QA: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing QA request: {str(e)}"
        )

@router.websocket("/qa/stream")
async def qa_stream_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming QA responses."""
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        req_dict = json.loads(data)
        req = QARequest(**req_dict)
        
        # Log the search query in search history
        db.add_search_history(req.question)
        
        llm_model = req.llm_model or settings.MODEL_NAME
        
        # 1. Retrieve context
        top_k = settings.TOP_K_DENSE
        if len(req.paper_ids) > 1:
            top_k = top_k * len(req.paper_ids)
            
        citations = retrieve_context(
            query=req.question,
            paper_ids=req.paper_ids,
            top_k=top_k
        )
        
        # Compute Confidence Score
        confidence_score = 0.0
        scores = [c["score"] for c in citations if "score" in c]
        if scores:
            avg_score = sum(scores) / len(scores)
            if settings.USE_RERANKER:
                confidence_score = float(1.0 / (1.0 + np.exp(-avg_score)))
            else:
                confidence_score = float(max(0.0, min(1.0, (avg_score + 1.0) / 2.0)))
        else:
            confidence_score = 0.70
            
        # Send citations and metadata first
        await websocket.send_json({
            "type": "meta",
            "citations": citations,
            "confidence_score": round(confidence_score, 2)
        })
        
        if not citations:
            await websocket.send_json({
                "type": "content",
                "text": "I cannot find sufficient evidence in the uploaded paper(s) because no relevant context could be retrieved."
            })
            await websocket.send_json({"type": "done"})
            return
            
        # 2. Build QA prompt
        system_prompt, user_prompt = build_qa_prompt(req.question, citations)
        
        # 3. Stream from LLM
        full_answer = ""
        stream = stream_llm(
            prompt=user_prompt,
            model_name=llm_model,
            system_prompt=system_prompt
        )
        
        for chunk in stream:
            full_answer += chunk
            await websocket.send_json({
                "type": "content",
                "text": chunk
            })
            # Yield to event loop to keep websocket alive
            await asyncio.sleep(0.01)
            
        await websocket.send_json({"type": "done"})
        
        # Log QA interaction in DB
        p_id = req.paper_ids[0] if len(req.paper_ids) == 1 else None
        db.add_qa_log(
            paper_id=p_id,
            question=req.question,
            answer=full_answer,
            citations=citations,
            confidence_score=round(confidence_score, 2)
        )
        
    except WebSocketDisconnect:
        logger.info("Client disconnected from QA stream")
    except Exception as e:
        logger.error(f"Error in QA stream: {str(e)}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
        except:
            pass

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
@router.post("/graph", response_model=GraphResponse)
async def generate_graph_endpoint(paper_ids: List[str] = Body(...)):
    """Generate or retrieve the knowledge graph for selected papers."""
    try:
        start_time = time.time()
        
        # 1. Ensure structured knowledge exists for each paper
        conn = db._get_connection()
        for pid in paper_ids:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM structured_knowledge WHERE paper_id = ?", (pid,))
            count = cursor.fetchone()["cnt"]
            if count == 0:
                # Extract knowledge on-demand for papers uploaded before auto-extraction
                paper_meta = db.get_paper(pid)
                if paper_meta and paper_meta.get("file_path"):
                    try:
                        logger.info(f"On-demand knowledge extraction for paper: {pid}")
                        from pathlib import Path
                        _, full_text = extract_pdf_data(Path(paper_meta["file_path"]))
                        extract_structured_knowledge(pid, full_text)
                    except Exception as ke:
                        logger.warning(f"On-demand extraction failed for {pid}: {ke}")
        conn.close()
        
        # 2. Build graph
        graph_manager.build_graph_for_papers(paper_ids)
        
        # 2. Load it
        graph = graph_store.load_graph(paper_ids)
        
        # 3. Format to JSON
        nodes = []
        for n, data in graph.nodes(data=True):
            data_copy = dict(data)
            data_copy["id"] = n
            nodes.append(data_copy)
            
        edges = []
        for u, v, data in graph.edges(data=True):
            data_copy = dict(data)
            data_copy["source"] = u
            data_copy["target"] = v
            edges.append(data_copy)
            
        latency = time.time() - start_time
        return GraphResponse(nodes=nodes, edges=edges, latency_sec=latency)
    except Exception as e:
        logger.error(f"Error generating graph: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating graph: {str(e)}"
        )

@router.post("/compare", response_model=CompareResponse)
async def compare_papers_endpoint(paper_ids: List[str] = Body(...)):
    """Compare multiple research papers."""
    try:
        if len(paper_ids) < 2:
            raise HTTPException(status_code=400, detail="At least two papers are required for comparison.")
            
        start_time = time.time()
        
        agent = ResearchAgent()
        import asyncio
        result = await agent.execute({"action": "compare", "paper_ids": paper_ids})
        
        latency = time.time() - start_time
        return CompareResponse(
            comparison_markdown=result.get("comparison_table", "Failed to generate comparison."),
            latency_sec=latency
        )
    except Exception as e:
        logger.error(f"Error comparing papers: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error comparing papers: {str(e)}"
        )


