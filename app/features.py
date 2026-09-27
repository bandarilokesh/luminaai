"""Features built on the RAG pipeline: summaries, quizzes, flashcards, comparison and research gaps.

Each feature retrieves (or samples) chunks from Qdrant, injects them as numbered context and asks
the LLM for a grounded answer.
"""
from typing import Any

from app.config import settings
from app.observability import observe
from app.rag import llm
from app.rag.prompts import (
    COMPARE_TEMPLATE,
    FLASHCARD_TEMPLATE,
    GAPS_TEMPLATE,
    GROUNDED_TASK_SYSTEM_PROMPT,
    QUIZ_FORMATS,
    QUIZ_TEMPLATE,
    SUMMARY_STYLES,
    SUMMARY_TEMPLATE,
    format_context,
)
from app.rag.retriever import retrieve
from app.rag.vector_store import get_vector_store


class FeatureError(ValueError):
    pass


def _dedupe(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen, unique = set(), []
    for chunk in chunks:
        key = (chunk["paper_id"], chunk["chunk_index"])
        if key not in seen:
            seen.add(key)
            unique.append(chunk)
    return unique


def _sample_evenly(chunks: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if len(chunks) <= count:
        return chunks
    step = len(chunks) / count
    return [chunks[int(i * step)] for i in range(count)]


def _paper_chunks(paper_id: str) -> list[dict[str, Any]]:
    chunks = get_vector_store().get_paper_chunks(paper_id)
    if not chunks:
        raise FeatureError(f"Paper {paper_id} has no indexed chunks. Re-upload it.")
    return chunks


def _coverage_context(paper_ids: list[str], chunks_per_paper: int = 12) -> str:
    """Chunks spread evenly across each paper, so study material covers the whole document."""
    budget = settings.CONTEXT_TOKEN_BUDGET // max(1, len(paper_ids))
    parts = []
    for paper_id in paper_ids:
        context, _ = format_context(_sample_evenly(_paper_chunks(paper_id), chunks_per_paper), budget)
        parts.append(context)
    return "\n\n===\n\n".join(parts)


def _retrieved_context(paper_ids: list[str], query: str, top_k: int = 6) -> tuple[str, list[str]]:
    """Top-k chunks per paper for a focused query, grouped by paper."""
    budget = settings.CONTEXT_TOKEN_BUDGET // max(1, len(paper_ids))
    parts, titles = [], []
    for paper_id in paper_ids:
        chunks = _paper_chunks(paper_id)
        hits = retrieve(query, [paper_id], top_k=top_k)
        hits.sort(key=lambda c: c["chunk_index"])
        context, _ = format_context(_dedupe(chunks[:1] + hits), budget)
        titles.append(chunks[0]["paper_name"])
        parts.append(f"## {chunks[0]['paper_name']}\n\n{context}")
    return "\n\n===\n\n".join(parts), titles


@observe(name="summary")
def summarize(paper_id: str, summary_type: str) -> str:
    style = SUMMARY_STYLES.get(summary_type)
    if not style:
        raise FeatureError(f"Unknown summary type '{summary_type}'. Choose from: {', '.join(SUMMARY_STYLES)}")
    chunks = _paper_chunks(paper_id)
    hits = retrieve(style["query"], [paper_id], top_k=10)
    # Opening chunks (title/abstract/introduction) + the chunks most relevant to this summary style.
    selected = _dedupe(chunks[:2] + sorted(hits, key=lambda c: c["chunk_index"]))
    context, _ = format_context(selected)
    prompt = SUMMARY_TEMPLATE.format(title=chunks[0]["paper_name"], context=context, instruction=style["instruction"])
    return llm.generate(GROUNDED_TASK_SYSTEM_PROMPT, prompt, name=f"summary-{summary_type}")


def _normalize_question(item: dict[str, Any], quiz_type: str) -> dict[str, Any] | None:
    question, answer = str(item.get("question", "")).strip(), str(item.get("answer", "")).strip()
    if not question or not answer:
        return None
    options = item.get("options") or None
    if quiz_type == "true_false":
        options = ["True", "False"]
        answer = "True" if answer.lower().startswith("t") else "False"
    elif quiz_type == "mcq":
        options = [str(o).strip() for o in (options or [])]
        if len(options) < 2:
            return None
        match = next((o for o in options if o.lower() == answer.lower()), None)
        if match is None and len(answer) == 1 and answer.upper() in "ABCD"[: len(options)]:
            match = options["ABCD".index(answer.upper())]  # model answered with a letter
        if match is None:
            match = next((o for o in options if answer.lower() in o.lower()), None)
        if match is None:
            return None
        answer = match
    else:
        options = None
    return {"question": question, "options": options, "answer": answer, "explanation": item.get("explanation") or None}


@observe(name="quiz")
def generate_quiz(paper_ids: list[str], quiz_type: str, difficulty: str, count: int) -> list[dict[str, Any]]:
    if quiz_type not in QUIZ_FORMATS:
        raise FeatureError(f"Unknown quiz type '{quiz_type}'. Choose from: {', '.join(QUIZ_FORMATS)}")
    prompt = QUIZ_TEMPLATE.format(
        context=_coverage_context(paper_ids),
        count=count,
        difficulty=difficulty,
        kind=quiz_type.replace("_", "-"),
        format_hint=QUIZ_FORMATS[quiz_type],
    )
    data = llm.generate_json(GROUNDED_TASK_SYSTEM_PROMPT, prompt, name="quiz")
    items = data.get("questions", []) if isinstance(data, dict) else data
    questions = [q for q in (_normalize_question(i, quiz_type) for i in items if isinstance(i, dict)) if q]
    if not questions:
        raise FeatureError("The model returned no usable questions. Please try again.")
    return questions[:count]


@observe(name="flashcards")
def generate_flashcards(paper_ids: list[str], count: int) -> list[dict[str, Any]]:
    prompt = FLASHCARD_TEMPLATE.format(context=_coverage_context(paper_ids), count=count)
    data = llm.generate_json(GROUNDED_TASK_SYSTEM_PROMPT, prompt, name="flashcards")
    items = data.get("cards", []) if isinstance(data, dict) else data
    cards = [
        {"front": str(c["front"]).strip(), "back": str(c["back"]).strip(), "explanation": c.get("explanation") or None}
        for c in items
        if isinstance(c, dict) and c.get("front") and c.get("back")
    ]
    if not cards:
        raise FeatureError("The model returned no usable flashcards. Please try again.")
    return cards[:count]


@observe(name="compare-papers")
def compare_papers(paper_ids: list[str]) -> str:
    if len(paper_ids) < 2:
        raise FeatureError("Select at least two papers to compare.")
    context, titles = _retrieved_context(
        paper_ids, "problem statement, proposed approach, datasets, key results, strengths and limitations"
    )
    prompt = COMPARE_TEMPLATE.format(context=context, titles="; ".join(titles))
    return llm.generate(GROUNDED_TASK_SYSTEM_PROMPT, prompt, name="compare-papers")


@observe(name="research-gaps")
def detect_research_gaps(paper_ids: list[str]) -> list[dict[str, Any]]:
    if not paper_ids:
        raise FeatureError("Select at least one paper.")
    context, _ = _retrieved_context(
        paper_ids, "limitations, threats to validity, assumptions, future work, open problems, missing experiments"
    )
    data = llm.generate_json(GROUNDED_TASK_SYSTEM_PROMPT, GAPS_TEMPLATE.format(context=context), name="research-gaps")
    items = data.get("gaps", []) if isinstance(data, dict) else data
    return [
        {
            "title": str(g.get("title", "Untitled gap")),
            "description": str(g.get("description", "")),
            "category": str(g.get("category", "future_work")),
            "papers": [str(p) for p in g.get("papers", []) or []],
            "confidence": str(g.get("confidence", "medium")).lower(),
            "suggestion": str(g.get("suggestion", "")),
        }
        for g in items
        if isinstance(g, dict)
    ]
