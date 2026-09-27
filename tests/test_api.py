import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests.conftest import SAMPLE_PAGES, make_pdf


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _upload(client, tmp_path, name="paper.pdf", title="Attention Based Retrieval for Papers"):
    pdf = make_pdf(tmp_path / name, SAMPLE_PAGES, title=title)
    with open(pdf, "rb") as f:
        res = client.post("/api/papers/upload", files={"file": (name, f, "application/pdf")})
    assert res.status_code == 201, res.text
    paper = client.get(f"/api/papers/{res.json()['id']}").json()  # background indexing has run
    assert paper["status"] == "completed", paper
    return paper


def test_health_and_spa(client):
    assert client.get("/health").json()["status"] == "healthy"
    assert "Lumina" in client.get("/library").text


def test_upload_rejects_non_pdf(client):
    res = client.post("/api/papers/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert res.status_code == 400


def test_full_flow(client, tmp_path, offline_models):
    paper = _upload(client, tmp_path)
    other = _upload(client, tmp_path, "second.pdf", "Keyword Search Baselines")
    assert paper["chunk_count"] > 0 and paper["page_count"] == 3
    assert paper["title"].startswith("Attention Based Retrieval")
    ids = [paper["id"], other["id"]]

    qa = client.post("/api/qa", json={"question": "How much does accuracy improve?", "paper_ids": [paper["id"]]})
    assert qa.status_code == 200, qa.text
    body = qa.json()
    assert body["answer"].startswith("Stub answer") and body["citations"]
    assert all(c["paper_id"] == paper["id"] for c in body["citations"])

    # empty paper_ids searches the whole library
    assert client.post("/api/qa", json={"question": "self-attention", "paper_ids": []}).json()["citations"]

    with client.stream("POST", "/api/qa/stream", json={"question": "What is self-attention?", "paper_ids": ids}) as res:
        events = [json.loads(line[6:]) for line in res.iter_lines() if line.startswith("data: ")]
    assert [e["type"] for e in events][0] == "meta" and events[-1]["type"] == "done"

    s1 = client.post("/api/summary", json={"paper_id": paper["id"], "summary_type": "methodology"}).json()
    s2 = client.post("/api/summary", json={"paper_id": paper["id"], "summary_type": "methodology"}).json()
    assert s1["cached"] is False and s2["cached"] is True and s1["summary_text"] == s2["summary_text"]
    assert client.post("/api/summary", json={"paper_id": paper["id"], "summary_type": "nope"}).status_code == 400

    quiz = client.post("/api/quiz", json={"paper_ids": ids, "quiz_type": "mcq", "num_questions": 3}).json()
    assert quiz["questions"][0]["answer"] in quiz["questions"][0]["options"]

    cards = client.post("/api/flashcards", json={"paper_ids": [paper["id"]], "num_cards": 3}).json()
    assert cards["cards"][0]["front"] == "Self-attention"

    compare = client.post("/api/compare", json=ids)
    assert compare.status_code == 200 and compare.json()["comparison_markdown"]
    assert client.post("/api/compare", json=[paper["id"]]).status_code == 400

    gaps = client.post("/api/gap-detector", json=ids).json()["gaps"]
    assert gaps[0]["confidence"] == "high" and gaps[0]["title"] == "Small datasets"

    stats = client.get("/api/stats").json()
    assert stats["questions_asked"] >= 3 and stats["summaries_generated"] == 1 and stats["study_sessions"] == 2
    assert client.get("/api/activity?limit=3").json()

    status = client.get("/api/status").json()
    assert status["vectors_stored"] >= paper["chunk_count"]
    assert {s["name"] for s in status["services"]} >= {"Qdrant", "Langfuse"}

    for pid in ids:
        assert client.delete(f"/api/papers/{pid}").json()["success"]
    assert client.get(f"/api/papers/{paper['id']}").status_code == 404
    assert client.post("/api/qa", json={"question": "x", "paper_ids": [paper["id"]]}).status_code == 404


def test_llm_errors_become_502(client, tmp_path, monkeypatch):
    from app.rag import llm

    paper = _upload(client, tmp_path, "err.pdf")

    def boom(*a, **k):
        raise llm.LLMError("groq rate limit")

    monkeypatch.setattr(llm, "generate", boom)
    res = client.post("/api/qa", json={"question": "self-attention?", "paper_ids": [paper["id"]]})
    assert res.status_code == 502 and "rate limit" in res.json()["detail"]
    client.delete(f"/api/papers/{paper['id']}")


def test_access_code_gate(client, monkeypatch):
    monkeypatch.setattr(settings, "ACCESS_CODE", "secret")
    assert client.get("/api/papers/").status_code == 401
    assert client.get("/").status_code == 401
    assert client.post("/api/auth/login", json={"code": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"code": "secret"}).status_code == 200
    assert client.get("/api/papers/").status_code == 200
    client.cookies.clear()
