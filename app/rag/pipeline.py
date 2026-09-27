"""Indexing pipeline (run once per document) and query pipeline (run for every question)."""
import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.logger import logger
from app.observability import langfuse, observe
from app.rag import llm
from app.rag.chunker import chunk_document
from app.rag.embeddings import embeddings
from app.rag.loader import LoadedDocument, load_pdf
from app.rag.prompts import NOT_FOUND_ANSWER, build_qa_prompt
from app.rag.retriever import retrieve, to_citation
from app.rag.vector_store import get_vector_store


@observe(name="index-paper")
def index_paper(paper_id: str, file_path: Path) -> tuple[LoadedDocument, int]:
    """Documents -> Loader -> Chunking -> Embedding model -> Vector database."""
    document = load_pdf(file_path)
    if not document.pages:
        raise ValueError("No extractable text found. Scanned/image-only PDFs are not supported.")

    chunks = chunk_document(document)
    vectors = embeddings.embed_documents([c.text for c in chunks])

    store = get_vector_store()
    store.delete_paper(paper_id)  # re-indexing replaces any previous points
    count = store.upsert_chunks(paper_id, document.title, chunks, vectors)

    langfuse.update_current_span(
        input={"paper_id": paper_id, "file": file_path.name},
        output={"title": document.title, "pages": document.page_count, "chunks": count},
    )
    logger.info(f"Indexed paper {paper_id}: {document.page_count} pages -> {count} chunks")
    return document, count


def _retrieval_score(chunks: list[dict[str, Any]]) -> float:
    """Mean cosine similarity of the retrieved chunks (0-1)."""
    if not chunks:
        return 0.0
    return round(max(0.0, min(1.0, sum(c["score"] for c in chunks) / len(chunks))), 3)


@observe(name="rag-qa")
def answer_question(question: str, paper_ids: list[str] | None = None) -> dict[str, Any]:
    """User query -> Query embedding -> Retriever -> Top-K chunks -> LLM -> Response."""
    start = time.perf_counter()
    chunks = retrieve(question, paper_ids)
    if not chunks:
        answer, used = NOT_FOUND_ANSWER, []
    else:
        system_prompt, user_prompt, used = build_qa_prompt(question, chunks)
        answer = llm.generate(system_prompt, user_prompt, name="qa-answer")
    return {
        "answer": answer,
        "citations": [to_citation(c) for c in used],
        "retrieval_score": _retrieval_score(used),
        "latency_sec": round(time.perf_counter() - start, 2),
        "trace_id": langfuse.get_current_trace_id(),
    }


async def stream_answer(question: str, paper_ids: list[str] | None = None) -> AsyncIterator[dict[str, Any]]:
    """Streaming variant of the query pipeline. Yields meta, token and done events."""
    start = time.perf_counter()
    with langfuse.start_as_current_observation(name="rag-qa-stream", as_type="chain", input={"question": question, "paper_ids": paper_ids}) as span:
        chunks = await asyncio.to_thread(retrieve, question, paper_ids)
        if not chunks:
            yield {"type": "meta", "citations": [], "retrieval_score": 0.0}
            yield {"type": "token", "text": NOT_FOUND_ANSWER}
            span.update(output=NOT_FOUND_ANSWER)
            yield {"type": "done", "answer": NOT_FOUND_ANSWER, "latency_sec": round(time.perf_counter() - start, 2)}
            return

        system_prompt, user_prompt, used = build_qa_prompt(question, chunks)
        citations = [to_citation(c) for c in used]
        yield {"type": "meta", "citations": citations, "retrieval_score": _retrieval_score(used)}

        parts: list[str] = []
        async for token in llm.stream(system_prompt, user_prompt, name="qa-answer-stream"):
            parts.append(token)
            yield {"type": "token", "text": token}
        answer = "".join(parts).strip()
        span.update(output=answer)
        yield {
            "type": "done",
            "answer": answer,
            "citations": citations,
            "retrieval_score": _retrieval_score(used),
            "latency_sec": round(time.perf_counter() - start, 2),
            "trace_id": langfuse.get_current_trace_id(),
        }
