import hashlib
import math
import os
import re
import tempfile
from pathlib import Path

# Configure an isolated, offline environment before the app is imported.
_TMP = Path(tempfile.mkdtemp(prefix="lumina-tests-"))
os.environ.update({
    "QDRANT_URL": ":memory:",
    "QDRANT_COLLECTION": "test_papers",
    "DATA_DIR": str(_TMP / "data"),
    "UPLOAD_DIR": str(_TMP / "uploads"),
    "LANGFUSE_PUBLIC_KEY": "",
    "LANGFUSE_SECRET_KEY": "",
    "ACCESS_CODE": "",
    "JINA_API_KEY": "test",
    "GROQ_API_KEY": "test",
    "LLM_PROVIDER": "groq",
    "EMBEDDING_DIM": "256",
})

import pymupdf  # noqa: E402
import pytest  # noqa: E402

from app.config import settings  # noqa: E402


def fake_vector(text: str) -> list[float]:
    """Deterministic bag-of-words embedding: texts sharing words get similar vectors."""
    vec = [0.0] * settings.EMBEDDING_DIM
    for word in re.findall(r"[a-z]{3,}", text.lower()):
        vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % len(vec)] = 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@pytest.fixture(autouse=True)
def offline_models(monkeypatch):
    from app.rag import llm
    from app.rag.embeddings import embeddings

    monkeypatch.setattr(embeddings, "embed_documents", lambda texts: [fake_vector(t) for t in texts])
    monkeypatch.setattr(embeddings, "embed_query", fake_vector)

    calls = []

    def fake_generate(system_prompt, user_prompt, *, name, json_mode=False, **_):
        calls.append({"name": name, "system": system_prompt, "user": user_prompt})
        if name == "quiz":
            return '{"questions": [{"question": "What does the transformer use?", "options": ["Attention", "Recurrence", "Convolution", "Trees"], "answer": "Attention", "explanation": "See [1]."}]}'
        if name == "flashcards":
            return '{"cards": [{"front": "Self-attention", "back": "Relates all tokens in the input.", "explanation": ""}]}'
        if name == "research-gaps":
            return '```json\n{"gaps": [{"title": "Small datasets", "description": "Only tested on one dataset.", "category": "limitation", "papers": ["A"], "confidence": "high", "suggestion": "More data."}]}\n```'
        return f"Stub answer for {name} [1]"

    async def fake_stream(system_prompt, user_prompt, *, name):
        calls.append({"name": name, "system": system_prompt, "user": user_prompt})
        for token in ["Streamed ", "answer ", "[1]"]:
            yield token

    monkeypatch.setattr(llm, "generate", fake_generate)
    monkeypatch.setattr(llm, "stream", fake_stream)
    return calls


def make_pdf(path: Path, pages: list[str], title: str = "Attention Based Retrieval for Papers") -> Path:
    doc = pymupdf.open()
    for i, body in enumerate(pages):
        page = doc.new_page()
        y = 72
        if i == 0:
            page.insert_text((72, y), title, fontsize=18)
            y += 36
        page.insert_text((72, 30), "Journal of Test Papers", fontsize=8)  # running header
        page.insert_textbox(pymupdf.Rect(72, y, 540, 760), body, fontsize=10)
        page.insert_text((300, 800), str(i + 1), fontsize=8)  # page number
    doc.set_metadata({"author": "Ada Lovelace"})
    doc.save(path)
    doc.close()
    return path


SAMPLE_PAGES = [
    "Abstract\nWe study retrieval augmented generation for research papers. Our method embeds chunks "
    "and retrieves them with cosine similarity.\n1 Introduction\nLarge language models hallucinate when "
    "they lack context. Retrieval grounds the answers in documents.",
    "2 Method\nThe transformer encoder uses self-attention to relate all tokens. We split documents with "
    "recursive chunking and store vectors in Qdrant with payload metadata.\n" + ("Detail sentence about the method. " * 60),
    "3 Results\nOur system improves answer accuracy by 12 percent on the benchmark dataset compared with "
    "keyword search.\n4 Conclusion\nGrounded generation reduces hallucinations. Future work includes tables.",
]


@pytest.fixture
def sample_pdf(tmp_path) -> Path:
    return make_pdf(tmp_path / "paper.pdf", SAMPLE_PAGES)
