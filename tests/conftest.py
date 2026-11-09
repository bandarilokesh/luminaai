import hashlib
import json
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
    "AUDIT_VERIFY_LINKS": "false",
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
        if name == "reproducibility-audit":
            return json.dumps(FAKE_AUDIT)
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


FAKE_AUDIT = {
    "dimensions": {
        "hyperparameters": {"score": 70, "items": [
            {"parameter": "Learning rate", "status": "specified", "value": "3e-4", "citation_page": 1, "risk_level": "low", "note": "Table 1."},
            {"parameter": "Random seeds", "status": "specified", "value": "42", "citation_page": 1, "risk_level": "low", "note": "Seed 42."},
            {"parameter": "Warmup", "status": "missing", "value": None, "citation_page": None, "risk_level": "medium", "note": "Not stated."},
        ]},
        "compute": {"score": 60, "items": [
            {"parameter": "Accelerator model", "status": "specified", "value": "8x A100", "citation_page": 2, "risk_level": "low", "note": "A100."},
            {"parameter": "Training time", "status": "missing", "value": None, "citation_page": None, "risk_level": "high", "note": "Not stated."},
        ]},
        "data": {"score": 60, "items": [
            {"parameter": "Split sizes", "status": "partial", "value": None, "citation_page": 2, "risk_level": "medium", "note": "Benchmark named only."},
        ]},
        "statistics": {"score": 25, "items": [
            {"parameter": "Variance reporting", "status": "missing", "value": None, "citation_page": None, "risk_level": "high", "note": "Single run."},
        ]},
        "artifacts": {"score": 90, "items": [
            {"parameter": "Public code repository", "status": "specified", "value": "github", "citation_page": None, "risk_level": "low", "note": "Claimed."},
        ]},
    },
    "missing_critical_parameters": ["Learning-rate warmup steps"],
    "potential_leakage_risks": ["No check that benchmark test data was excluded from tuning."],
    "recipe": {"model_name": "ours-base", "parameter_count_billions": 0.11, "framework": "PyTorch", "hardware": "8x NVIDIA A100",
               "arguments": {"learning_rate": "3e-4", "batch_size": "64", "seed": "42"}},
}


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


def _draw_row(page, y: float, cells: list[str], xs: list[float], fontsize: float = 9) -> None:
    for x, text in zip(xs, cells):
        page.insert_text((x, y), text, fontsize=fontsize)


def make_table_pdf(path: Path) -> Path:
    """Two-page PDF: a fully ruled grid table and a LaTeX booktabs-style table (horizontal rules only)."""
    doc = pymupdf.open()

    # Page 1: ruled grid with a caption above.
    page = doc.new_page()
    page.insert_text((72, 72), "Ruled Table Paper", fontsize=16)
    page.insert_text((72, 110), "Table 1: Hyperparameters used for training.", fontsize=9)
    grid = [["Parameter", "Value"], ["Learning rate", "3e-4"], ["Batch size", "64"], ["Seed", "42"]]
    left, right, top, row_h = 72, 372, 120, 20
    xs = [left, 222, right]
    for i in range(len(grid) + 1):
        page.draw_line((left, top + i * row_h), (right, top + i * row_h))
    for x in xs:
        page.draw_line((x, top), (x, top + len(grid) * row_h))
    for i, row in enumerate(grid):
        _draw_row(page, top + i * row_h + 14, row, [left + 4, 226])

    # Page 2: booktabs table (top/mid/bottom rules), caption above.
    page = doc.new_page()
    page.insert_text((72, 72), "Table 2: Results on the benchmark (accuracy %).", fontsize=9)
    cols = [72, 220, 320, 420]
    page.draw_line((72, 84), (500, 84), width=0.8)
    _draw_row(page, 98, ["Model", "MNLI", "QNLI", "F1"], cols)
    page.draw_line((72, 104), (500, 104), width=0.5)
    body = [["Baseline", "84.1", "90.2", "88.0"], ["Ours", "86.7", "92.5", "90.3"], ["Ours (no attn)", "85.0", "91.1", "89.2"]]
    for i, row in enumerate(body):
        _draw_row(page, 120 + i * 16, row, cols)
    page.draw_line((72, 160), (500, 160), width=0.8)
    page.insert_textbox(pymupdf.Rect(72, 190, 500, 400), "We trained on 8 NVIDIA A100 GPUs with seed 42.", fontsize=10)

    doc.save(path)
    doc.close()
    return path
