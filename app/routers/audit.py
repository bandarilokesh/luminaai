"""Reproducibility audit (Novelty 2) and extracted tables (Novelty 4) endpoints."""
import re
import time

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.db import db
from app.logger import logger
from app.rag import llm
from app.rag.embeddings import EmbeddingError
from app.rag.reproducibility import AuditError, report_to_markdown, run_audit
from app.schemas import PaperTablesResponse, ReproducibilityReport

router = APIRouter(tags=["Reproducibility & Tables"])


def _completed_paper(paper_id: str) -> dict:
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Paper {paper_id} not found.")
    if paper["status"] != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, f"'{paper['title']}' is still {paper['status']}.")
    return paper


def _generate(paper: dict) -> dict:
    start = time.perf_counter()
    try:
        report = run_audit(paper["id"], paper["title"], db.get_paper_tables(paper["id"]))
    except AuditError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except (llm.LLMError, EmbeddingError) as e:
        logger.error(f"Reproducibility audit failed for {paper['id']}: {e}")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    db.save_audit(paper["id"], report)
    db.log_activity("audit", f"Audited {paper['title'][:60]}: {report['overall_score']:.0f}/100 ({report['grade']})", paper["id"])
    return {**report, "cached": False, "latency_sec": round(time.perf_counter() - start, 2)}


@router.get("/audit/{paper_id}", response_model=ReproducibilityReport)
def get_audit(paper_id: str, generate: bool = True):
    """Cached reproducibility audit, generated on first request (generate=false: cache lookup only, 404 if none)."""
    paper = _completed_paper(paper_id)
    cached = db.get_audit(paper_id)
    if cached:
        return {**cached, "cached": True, "latency_sec": 0.0}
    if not generate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No audit has been run for this paper yet.")
    return _generate(paper)


@router.post("/audit/{paper_id}/refresh", response_model=ReproducibilityReport)
def refresh_audit(paper_id: str):
    """Force a re-run of the 5-dimension audit with the current LLM."""
    return _generate(_completed_paper(paper_id))


@router.get("/audit/{paper_id}/export")
def export_audit(paper_id: str):
    """Peer-reviewer scorecard as a Markdown download."""
    paper = _completed_paper(paper_id)
    report = db.get_audit(paper_id) or _generate(paper)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", paper["title"])[:60].strip("_") or "paper"
    return Response(
        report_to_markdown(report),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}_repro_scorecard.md"'},
    )


@router.get("/tables/{paper_id}", response_model=PaperTablesResponse)
def get_tables(paper_id: str):
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Paper {paper_id} not found.")
    return PaperTablesResponse(paper_id=paper_id, paper_title=paper["title"], tables=db.get_paper_tables(paper_id))
