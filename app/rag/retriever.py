"""Retriever: semantic (dense) search over Qdrant with metadata filtering by paper.

Hybrid multimodal routing: narrative chunks are always searched; the table collection is also
searched when the query is empirical (results, metrics, numbers, comparisons) or when the
caller forces it (table QA). Table hits are shaped like chunks (kind="table") so prompts and
citations handle both streams uniformly.
"""
import re
from typing import Any

from app.config import settings
from app.observability import langfuse, observe
from app.rag.embeddings import embeddings
from app.rag.vector_store import get_vector_store

TABULAR_KEYWORDS = (
    "table", "result", "accuracy", "f1", "bleu", "rouge", "latency", "benchmark", "ablation", "comparison",
    "compare", "performance", "%", "baseline", "score", "metric", "hyperparameter", "learning rate",
    "batch size", "dataset size", "how many", "how much", "number of", "precision", "recall", "auc",
    "perplexity", "error rate", "outperform", "sota", "state of the art", "speed", "throughput",
)
_TABULAR_RE = re.compile("|".join(rf"\b{re.escape(k)}" if k[0].isalnum() else re.escape(k) for k in TABULAR_KEYWORDS))
_MAX_TABLE_CHARS = 6000


def needs_tables(query: str) -> bool:
    """Is the question empirical/numeric enough that structured tables should be consulted?"""
    q = query.lower()
    return bool(_TABULAR_RE.search(q) or re.search(r"\d", q))


def table_hit_to_chunk(hit: dict[str, Any]) -> dict[str, Any]:
    markdown = hit.get("markdown", "")
    if len(markdown) > _MAX_TABLE_CHARS:
        markdown = markdown[:_MAX_TABLE_CHARS].rsplit("\n", 1)[0] + "\n| ... |"
    return {
        "id": hit.get("id"),
        "score": hit.get("score", 0.0),
        "kind": "table",
        "paper_id": hit["paper_id"],
        "paper_name": hit["paper_name"],
        "page": hit["page"],
        "section": hit.get("caption") or f"Table {hit['table_index']}",
        "table_index": hit["table_index"],
        "chunk_index": -int(hit["table_index"]),
        "text": markdown,
    }


def _log(hits: list[dict[str, Any]]) -> None:
    langfuse.update_current_span(
        output=[
            {"kind": h.get("kind", "text"), "paper": h["paper_name"], "page": h["page"],
             "score": round(h["score"], 4), "text": h["text"][:200]}
            for h in hits
        ]
    )


@observe(name="retrieve", as_type="retriever")
def retrieve(query: str, paper_ids: list[str] | None = None, top_k: int = settings.TOP_K) -> list[dict[str, Any]]:
    """1. Convert the query into an embedding. 2. Compare it with stored vectors (cosine).
    3. Return the top-k most similar chunks."""
    query_vector = embeddings.embed_query(query)
    hits = get_vector_store().search(
        query_vector, paper_ids=paper_ids, limit=top_k, score_threshold=settings.SCORE_THRESHOLD
    )
    _log(hits)
    return hits


@observe(name="retrieve-multimodal", as_type="retriever")
def retrieve_multimodal(
    query: str,
    paper_ids: list[str] | None = None,
    top_k_text: int = settings.TOP_K,
    top_k_tables: int = settings.TOP_K_TABLES,
    force_tables: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Text chunks + (when the query is tabular) table hits, sharing one query embedding."""
    query_vector = embeddings.embed_query(query)
    store = get_vector_store()
    text_hits = store.search(query_vector, paper_ids=paper_ids, limit=top_k_text, score_threshold=settings.SCORE_THRESHOLD)
    table_hits: list[dict[str, Any]] = []
    if top_k_tables > 0 and (force_tables or needs_tables(query)):
        raw = store.search_tables(query_vector, paper_ids=paper_ids, limit=top_k_tables, score_threshold=settings.SCORE_THRESHOLD)
        table_hits = [table_hit_to_chunk(h) for h in raw]
    _log(text_hits + table_hits)
    return text_hits, table_hits


def to_citation(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "paper_id": chunk["paper_id"],
        "paper_name": chunk["paper_name"],
        "page": chunk["page"],
        "section": chunk.get("section"),
        "chunk_id": chunk.get("id") or f"{chunk['paper_id']}:{chunk['chunk_index']}",
        "text_snippet": chunk["text"],
        "score": round(float(chunk.get("score", 0.0)), 4),
        "kind": chunk.get("kind", "text"),
        "table_index": chunk.get("table_index"),
    }
