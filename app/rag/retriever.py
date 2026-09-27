"""Retriever: semantic (dense) search over Qdrant with metadata filtering by paper."""
from typing import Any

from app.config import settings
from app.observability import langfuse, observe
from app.rag.embeddings import embeddings
from app.rag.vector_store import get_vector_store


@observe(name="retrieve", as_type="retriever")
def retrieve(query: str, paper_ids: list[str] | None = None, top_k: int = settings.TOP_K) -> list[dict[str, Any]]:
    """1. Convert the query into an embedding. 2. Compare it with stored vectors (cosine).
    3. Return the top-k most similar chunks."""
    query_vector = embeddings.embed_query(query)
    hits = get_vector_store().search(
        query_vector, paper_ids=paper_ids, limit=top_k, score_threshold=settings.SCORE_THRESHOLD
    )
    langfuse.update_current_span(
        output=[
            {"paper": h["paper_name"], "page": h["page"], "score": round(h["score"], 4), "text": h["text"][:200]}
            for h in hits
        ]
    )
    return hits


def to_citation(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "paper_id": chunk["paper_id"],
        "paper_name": chunk["paper_name"],
        "page": chunk["page"],
        "section": chunk.get("section"),
        "chunk_id": chunk.get("id") or f"{chunk['paper_id']}:{chunk['chunk_index']}",
        "text_snippet": chunk["text"],
        "score": round(float(chunk.get("score", 0.0)), 4),
    }
