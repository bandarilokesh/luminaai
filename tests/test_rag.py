import asyncio

from app.rag.chunker import RecursiveChunker, chunk_document, count_tokens
from app.rag.loader import clean_page, detect_heading, load_pdf
from app.rag.pipeline import answer_question, index_paper, stream_answer
from app.rag.prompts import NOT_FOUND_ANSWER, format_context
from app.rag.vector_store import get_vector_store, point_id


def test_loader_extracts_metadata_and_cleans(sample_pdf):
    doc = load_pdf(sample_pdf)
    assert doc.page_count == 3
    assert "Attention Based Retrieval" in doc.title
    assert doc.authors == "Ada Lovelace"
    assert doc.abstract.startswith("We study retrieval")
    full = doc.full_text
    assert "Journal of Test Papers" not in full  # repeated header removed
    assert doc.pages[2].section == "Method"  # section carried over from page 2


def test_clean_page_fixes_hyphenation_and_page_numbers():
    text = clean_page("The trans-\nformer   works.\n\n\n\n12\nNext line", set())
    assert "transformer works." in text
    assert "\n12\n" not in text
    assert "\n\n\n" not in text


def test_detect_heading():
    assert detect_heading("3.2 Experimental Setup") == "Experimental Setup"
    assert detect_heading("ABSTRACT") == "Abstract"
    assert detect_heading("This is an ordinary sentence in a paragraph.") is None


def test_recursive_chunker_respects_size_and_overlap():
    chunker = RecursiveChunker(chunk_size=50, chunk_overlap=10)
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 40 for i in range(6))
    chunks = chunker.split_text(text)
    assert len(chunks) > 3
    assert all(count_tokens(c) <= 50 for c in chunks)
    # consecutive chunks share overlapping text
    merged_small = chunker.split_text("One. Two. Three. Four. Five. Six. " * 20)
    assert any(a.split()[-1] in b for a, b in zip(merged_small, merged_small[1:]))


def test_chunk_document_keeps_page_and_section(sample_pdf):
    chunks = chunk_document(load_pdf(sample_pdf), RecursiveChunker(chunk_size=120, chunk_overlap=20))
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert {c.page for c in chunks} == {1, 2, 3}
    assert any(c.section == "Results" for c in chunks)


def test_vector_store_crud(sample_pdf):
    store = get_vector_store()
    doc, count = index_paper("paper-a", sample_pdf)
    assert count > 0
    assert store.info()["vector_size"] > 0
    assert len(store.get_paper_chunks("paper-a")) == count

    # upsert with the same IDs overwrites instead of duplicating
    index_paper("paper-a", sample_pdf)
    assert len(store.get_paper_chunks("paper-a")) == count
    assert point_id("paper-a", 0) == point_id("paper-a", 0)

    from tests.conftest import fake_vector
    hits = store.search(fake_vector("self-attention transformer tokens"), paper_ids=["paper-a"], limit=2)
    assert hits and hits[0]["page"] == 2
    assert store.search(fake_vector("transformer"), paper_ids=["other"], limit=2) == []

    store.delete_paper("paper-a")
    assert store.get_paper_chunks("paper-a") == []


def test_answer_question_grounds_prompt_in_context(sample_pdf, offline_models):
    index_paper("paper-b", sample_pdf)
    result = answer_question("How much does accuracy improve on the benchmark?", ["paper-b"])
    assert result["answer"].startswith("Stub answer")
    assert result["citations"] and result["citations"][0]["paper_id"] == "paper-b"
    assert 0 < result["retrieval_score"] <= 1
    prompt = offline_models[-1]["user"]
    assert "Context:" in prompt and "Question:" in prompt and "12 percent" in prompt
    assert "Answer only using the provided context" in offline_models[-1]["system"]
    get_vector_store().delete_paper("paper-b")


def test_answer_question_without_context_says_i_dont_know(offline_models):
    result = answer_question("anything", ["missing-paper"])
    assert result["answer"] == NOT_FOUND_ANSWER
    assert offline_models == []  # LLM never called


def test_stream_answer_events(sample_pdf):
    index_paper("paper-c", sample_pdf)

    async def collect():
        return [e async for e in stream_answer("What is self-attention?", ["paper-c"])]

    events = asyncio.run(collect())
    assert events[0]["type"] == "meta" and events[0]["citations"]
    assert "".join(e["text"] for e in events if e["type"] == "token") == "Streamed answer [1]"
    assert events[-1]["type"] == "done" and events[-1]["answer"] == "Streamed answer [1]"
    get_vector_store().delete_paper("paper-c")


def test_format_context_respects_budget():
    chunks = [{"paper_name": "P", "page": i, "section": "S", "text": "x" * 400} for i in range(10)]
    context, used = format_context(chunks, budget_tokens=250)
    assert len(used) == 2
    assert context.startswith("[1] P | page 0 | S")
