import json
import time
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status
from fastapi.responses import StreamingResponse

from app import features
from app.config import settings
from app.db import db
from app.logger import logger
from app.observability import TRACING_ENABLED, langfuse_status
from app.rag import llm
from app.rag.embeddings import EmbeddingError, embeddings
from app.rag.pipeline import answer_question, stream_answer
from app.rag.vector_store import get_vector_store
from app.schemas import (
    Activity,
    CompareResponse,
    FlashcardRequest,
    FlashcardResponse,
    QARequest,
    QAResponse,
    QuizRequest,
    QuizResponse,
    ResearchGapResponse,
    ServiceStatus,
    Stats,
    SummaryRequest,
    SummaryResponse,
    SystemStatus,
)

router = APIRouter(tags=["RAG"])


def _run(action: Callable[[], Any]) -> Any:
    """Map expected failures to clear HTTP errors for the UI."""
    try:
        return action()
    except features.FeatureError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except (llm.LLMError, EmbeddingError) as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e


def _require_papers(paper_ids: list[str]) -> None:
    for paper_id in paper_ids:
        paper = db.get_paper(paper_id)
        if not paper:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Paper {paper_id} not found.")
        if paper["status"] != "completed":
            raise HTTPException(status.HTTP_409_CONFLICT, f"'{paper['title']}' is still {paper['status']}.")


@router.post("/qa", response_model=QAResponse)
def ask(req: QARequest):
    _require_papers(req.paper_ids)
    result = _run(lambda: answer_question(req.question, req.paper_ids or None))
    db.add_qa_log(req.paper_ids, req.question, result)
    return result


@router.post("/qa/stream")
async def ask_stream(req: QARequest):
    """Server-sent events: meta (citations) -> token* -> done (or error)."""
    _require_papers(req.paper_ids)

    async def events():
        try:
            async for event in stream_answer(req.question, req.paper_ids or None):
                if event["type"] == "done":
                    db.add_qa_log(req.paper_ids, req.question, event)
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"QA stream failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/summary", response_model=SummaryResponse)
def summary(req: SummaryRequest):
    _require_papers([req.paper_id])
    start = time.perf_counter()
    cached = None if req.refresh else db.get_summary(req.paper_id, req.summary_type)
    text = cached or _run(lambda: features.summarize(req.paper_id, req.summary_type))
    if not cached:
        db.save_summary(req.paper_id, req.summary_type, text)
        db.log_activity("summary", f"Generated {req.summary_type} summary", req.paper_id)
    return SummaryResponse(
        paper_id=req.paper_id,
        summary_type=req.summary_type,
        summary_text=text,
        cached=bool(cached),
        latency_sec=round(time.perf_counter() - start, 2),
    )


@router.post("/quiz", response_model=QuizResponse)
def quiz(req: QuizRequest):
    _require_papers(req.paper_ids)
    start = time.perf_counter()
    questions = _run(lambda: features.generate_quiz(req.paper_ids, req.quiz_type, req.difficulty, req.num_questions))
    db.log_activity("quiz", f"Generated a {len(questions)}-question {req.difficulty} quiz")
    return QuizResponse(
        quiz_type=req.quiz_type,
        difficulty=req.difficulty,
        questions=questions,
        latency_sec=round(time.perf_counter() - start, 2),
    )


@router.post("/flashcards", response_model=FlashcardResponse)
def flashcards(req: FlashcardRequest):
    _require_papers(req.paper_ids)
    start = time.perf_counter()
    cards = _run(lambda: features.generate_flashcards(req.paper_ids, req.num_cards))
    db.log_activity("flashcards", f"Generated {len(cards)} flashcards")
    return FlashcardResponse(cards=cards, latency_sec=round(time.perf_counter() - start, 2))


@router.post("/compare", response_model=CompareResponse)
def compare(paper_ids: list[str] = Body(...)):
    _require_papers(paper_ids)
    start = time.perf_counter()
    markdown = _run(lambda: features.compare_papers(paper_ids))
    db.log_activity("compare", f"Compared {len(paper_ids)} papers")
    return CompareResponse(comparison_markdown=markdown, latency_sec=round(time.perf_counter() - start, 2))


@router.post("/gap-detector", response_model=ResearchGapResponse)
def gap_detector(paper_ids: list[str] = Body(...)):
    _require_papers(paper_ids)
    start = time.perf_counter()
    gaps = _run(lambda: features.detect_research_gaps(paper_ids))
    db.log_activity("gaps", f"Found {len(gaps)} research gaps across {len(paper_ids)} papers")
    return ResearchGapResponse(gaps=gaps, latency_sec=round(time.perf_counter() - start, 2))


@router.get("/stats", response_model=Stats)
def stats():
    return db.stats()


@router.get("/activity", response_model=list[Activity])
def activity(limit: int = 10):
    return db.recent_activity(limit)


@router.get("/status", response_model=SystemStatus)
def system_status():
    services = []
    vectors = 0
    try:
        info = get_vector_store().info()
        vectors = info["points_count"]
        services.append(ServiceStatus(
            name="Qdrant", status="ok",
            detail=f"{settings.QDRANT_URL} - {vectors} vectors, {info['vector_size']}-dim {info['distance']}",
        ))
    except Exception as e:
        services.append(ServiceStatus(name="Qdrant", status="error", detail=f"Unreachable at {settings.QDRANT_URL}: {e}"[:200]))

    services.append(ServiceStatus(
        name=f"LLM ({settings.LLM_PROVIDER})",
        status="ok" if llm.is_configured() else "error",
        detail=settings.llm_model if llm.is_configured() else "API key missing in .env",
    ))
    services.append(ServiceStatus(
        name="Embeddings (Jina AI)",
        status="ok" if embeddings.is_configured() else "error",
        detail=settings.EMBEDDING_MODEL if embeddings.is_configured() else "JINA_API_KEY missing in .env",
    ))
    lf = langfuse_status()
    services.append(ServiceStatus(
        name="Langfuse", status={"Connected": "ok", "Disabled": "warning"}.get(lf, "error"),
        detail=f"{lf} - {settings.LANGFUSE_BASE_URL}",
    ))
    return SystemStatus(
        app_name=settings.APP_NAME,
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.llm_model,
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_dim=settings.EMBEDDING_DIM,
        collection=settings.QDRANT_COLLECTION,
        vectors_stored=vectors,
        total_papers=len(db.list_papers()),
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        top_k=settings.TOP_K,
        tracing_enabled=TRACING_ENABLED,
        services=services,
    )
