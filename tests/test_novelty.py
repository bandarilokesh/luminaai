"""Novelty 4 (dual-stream table & equation engine) and Novelty 2 (reproducibility audit)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag import reproducibility as repro
from app.rag.loader import is_display_equation, normalize_math, _normalize
from app.rag.pipeline import answer_question, index_paper
from app.rag.prompts import format_context
from app.rag.retriever import needs_tables
from app.rag.table_extractor import clean_matrix, extract_tables_from_pdf, split_header, to_markdown, words_to_matrix
from app.rag.vector_store import get_vector_store
from tests.conftest import FAKE_AUDIT, fake_vector, make_table_pdf


@pytest.fixture
def table_pdf(tmp_path):
    return make_table_pdf(tmp_path / "tables.pdf")


# ---------------------------------------------------------------------------
# Novelty 4: table extraction
# ---------------------------------------------------------------------------
def test_extracts_ruled_and_booktabs_tables_with_captions(table_pdf):
    tables = extract_tables_from_pdf(table_pdf)
    assert [t.page for t in tables] == [1, 2]

    ruled, booktabs = tables
    assert ruled.caption.startswith("Table 1: Hyperparameters")
    assert ruled.headers == ["Parameter", "Value"]
    assert ["Learning rate", "3e-4"] in ruled.rows and ["Seed", "42"] in ruled.rows

    assert booktabs.caption.startswith("Table 2: Results")
    assert booktabs.headers == ["Model", "MNLI", "QNLI", "F1"]
    assert booktabs.rows[1] == ["Ours", "86.7", "92.5", "90.3"]
    assert ["Ours (no attn)", "85.0", "91.1", "89.2"] in booktabs.rows  # multi-word cell kept intact

    # Markdown grid has zero corrupted columns: every line has the header's column count.
    for t in tables:
        widths = {line.count(" | ") for line in t.markdown.splitlines()}
        assert widths == {len(t.headers) - 1}
        assert t.json_data["headers"] == t.headers and len(t.json_data["bbox"]) == 4


def test_clean_matrix_and_merged_headers():
    raw = [["GLUE", None, "", "SQuAD"], ["Model", "MNLI", "QNLI", "F1"], ["Ours", "86.7", "92.5", "90.3"], [None, None, None, None]]
    matrix = clean_matrix(raw)
    assert len(matrix) == 3  # empty row dropped
    headers, rows = split_header([["", "GLUE", "", "SQuAD"], ["Model", "MNLI", "QNLI", "F1"], ["Ours", "86.7", "92.5", "90.3"]])
    assert headers == ["Model", "GLUE MNLI", "GLUE QNLI", "SQuAD F1"]
    assert rows == [["Ours", "86.7", "92.5", "90.3"]]
    assert to_markdown(["a|b", "c"], [["1", "2"]]).splitlines()[0] == "| a\\|b | c |"


def test_words_to_matrix_infers_columns_from_shared_whitespace():
    def word(text, x0, top):
        return {"text": text, "x0": x0, "x1": x0 + 6 * len(text), "top": top}

    words = [word("Model", 10, 0), word("Acc", 120, 0),
             word("Big", 10, 12), word("model", 32, 12), word("91.2", 120, 12),
             word("Small", 10, 24), word("88.0", 120, 24)]
    assert words_to_matrix(words) == [["Model", "Acc"], ["Big model", "91.2"], ["Small", "88.0"]]


# ---------------------------------------------------------------------------
# Novelty 4: LaTeX normalizer
# ---------------------------------------------------------------------------
def test_math_normalizer_display_and_inline():
    assert is_display_equation("L(θ) = ∑ i ℓ(x i ) (3)")
    assert not is_display_equation("We minimize the loss of the model with θ = 1")
    out = normalize_math("L(θ) = ∑ i ℓ(x i ) (3)")
    assert out.startswith("$$ ") and r"\theta" in out and r"\sum" in out and r"\tag{3}" in out

    inline = _normalize("where θ ∈ ℝ d and β1 = 0.9 controls momentum.")
    assert r"$\theta \in \mathbb{R}$" in inline and r"$\beta_{1}$" in inline

    assert _normalize("It costs $5 with α decay.") == "It costs $5 with α decay."  # currency lines untouched
    assert _normalize("Plain text, nothing to do.") == "Plain text, nothing to do."
    assert _normalize("Real numbers ℝ only.").endswith(r"$\mathbb{R}$ only.")


# ---------------------------------------------------------------------------
# Novelty 4: hybrid multimodal retrieval
# ---------------------------------------------------------------------------
def test_needs_tables_routing():
    assert needs_tables("What accuracy does the model reach on MNLI?")
    assert needs_tables("Compare the baselines")
    assert not needs_tables("What is the main idea of the paper?")


def test_tables_indexed_and_retrieved_for_tabular_questions(table_pdf, offline_models):
    document, _ = index_paper("paper-t", table_pdf)
    assert len(document.tables) == 2
    store = get_vector_store()
    hits = store.search_tables(fake_vector("Results benchmark accuracy MNLI QNLI"), paper_ids=["paper-t"], limit=1)
    assert hits and hits[0]["table_index"] == 2 and "| Ours | 86.7 |" in hits[0]["markdown"]

    result = answer_question("What accuracy does Ours reach on the MNLI benchmark?", ["paper-t"])
    kinds = {c["kind"] for c in result["citations"]}
    assert "table" in kinds and "text" in kinds
    prompt = offline_models[-1]["user"]
    assert "TABLE 2 |" in prompt and "| Ours | 86.7 | 92.5 | 90.3 |" in prompt
    assert "cell-level precision" in offline_models[-1]["system"]

    table_mode = answer_question("Which model is best?", ["paper-t"], table_mode=True)
    assert table_mode["citations"][0]["kind"] == "table"
    assert offline_models[-1]["name"] == "qa-table-answer"

    store.delete_paper("paper-t")
    assert store.search_tables(fake_vector("results"), paper_ids=["paper-t"]) == []


def test_format_context_labels_tables():
    chunks = [{"kind": "table", "table_index": 3, "paper_name": "P", "page": 4, "section": "Table 3: Ablation", "text": "| a | b |"}]
    context, _ = format_context(chunks)
    assert context.startswith("[1] TABLE 3 | P | page 4 | Table 3: Ablation")


# ---------------------------------------------------------------------------
# Novelty 2: reproducibility scoring
# ---------------------------------------------------------------------------
def test_scan_signals_detects_evidence():
    text = ("Code is available at https://github.com/org/repo. We train on 8 NVIDIA A100 GPUs for 12 GPU-hours "
            "with random seed 42, averaged over 5 runs (86.1 ± 0.3, p < 0.05). Dedup removed overlap with the test set.")
    s = repro.scan_signals(text)
    assert s["repo_urls"] == ["https://github.com/org/repo"]
    assert "A100" in s["accelerator_names"]
    assert s["seed"] and s["variance"] and s["multiple_runs"] and s["significance"] and s["contamination"]
    assert repro.scan_signals("Code will be made available upon publication.")["code_promise"] == 1


def test_grades_and_dimension_scoring():
    assert sum(d.weight for d in repro.DIMENSIONS) == pytest.approx(1.0)
    assert [repro.grade_for(s)[0] for s in (95, 85, 75, 60, 45, 10)] == ["A+", "A", "B", "C", "D", "F"]
    items = [{"status": "specified"}, {"status": "missing"}]
    assert repro.score_dimension(80, items) == 65.0  # 0.5*80 + 0.5*50
    assert repro.score_dimension("n/a", items) == 50.0
    assert repro.score_dimension(140, []) == 100.0
    assert repro.estimate_vram_gb(7) == {"inference_gb": 16.8, "training_gb": 134.4}
    assert repro.estimate_vram_gb(None) is None


def test_build_report_caps_artifacts_without_repository():
    signals = repro.scan_signals("We train with seed 42.")
    report = repro.build_report("p1", "Paper", FAKE_AUDIT, signals, links=[])
    artifacts = next(c for c in report["categories"] if c["key"] == "artifacts")
    assert artifacts["score"] == 10.0  # LLM claimed 90, but no URL anywhere in the paper
    assert artifacts["items"][0]["parameter"] == "Repository URL"

    expected = round(sum(c["score"] * c["weight"] for c in report["categories"]), 1)
    assert report["overall_score"] == expected and report["grade"] == repro.grade_for(expected)[0]

    assert [repro.link_state(s) for s in (200, 301, 404, 410, 403, 429, 504)] == [True, True, False, False, None, None, None]
    unverified = [{"url": "https://github.com/x/y", "live": None, "status": "unreachable (ReadTimeout)"}]
    timed_out = repro.build_report("p1", "Paper", FAKE_AUDIT, repro.scan_signals("https://github.com/x/y"), unverified)
    art = next(c for c in timed_out["categories"] if c["key"] == "artifacts")
    assert art["score"] > 20 and art["items"][0]["status"] == "partial"  # a timeout is not a dead link

    dead = [{"url": "https://github.com/x/y", "live": False, "status": "404"}]
    with_dead_link = repro.build_report("p1", "Paper", FAKE_AUDIT, repro.scan_signals("https://github.com/x/y"), dead)
    art = next(c for c in with_dead_link["categories"] if c["key"] == "artifacts")
    assert art["score"] <= 20 and art["items"][0]["status"] == "missing"


def test_recipe_and_reviewer_export():
    markdown, command, hardware = repro.synthesize_recipe(FAKE_AUDIT["recipe"], ["Warmup steps"])
    assert "--learning_rate 3e-4" in command and "--seed 42" in command and "--weight_decay <SWEEP>" in command
    assert "8x NVIDIA A100" in hardware and "est. VRAM" in hardware
    assert "`weight_decay` is not reported" in markdown and "- Warmup steps" in markdown

    report = repro.build_report("p1", "Paper", FAKE_AUDIT, repro.scan_signals(""), [])
    scorecard = repro.report_to_markdown(report)
    assert scorecard.startswith("# Reproducibility Scorecard: Paper")
    assert "| Hyperparameter Completeness (HCI) | 25% |" in scorecard
    assert "[x] **Learning rate** = `3e-4` (p. 1)" in scorecard and "## Reproduction Recipe" in scorecard


def test_malformed_llm_output_degrades_gracefully():
    report = repro.build_report("p1", "Paper", {"dimensions": {"compute": "oops"}}, repro.scan_signals(""), [])
    assert len(report["categories"]) == 5
    assert all(i["status"] == "missing" for c in report["categories"] for i in c["items"])
    assert report["grade"] == "F"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_tables_audit_and_table_qa_endpoints(client, table_pdf, offline_models):
    with open(table_pdf, "rb") as f:
        res = client.post("/api/papers/upload", files={"file": ("tables.pdf", f, "application/pdf")})
    paper_id = res.json()["id"]
    assert client.get(f"/api/papers/{paper_id}").json()["status"] == "completed"

    tables = client.get(f"/api/tables/{paper_id}").json()["tables"]
    assert [t["table_index"] for t in tables] == [1, 2]
    assert tables[1]["headers"] == ["Model", "MNLI", "QNLI", "F1"]

    qa = client.post("/api/qa/table", json={"question": "Best F1 score?", "paper_ids": [paper_id]}).json()
    assert qa["citations"][0]["kind"] == "table" and qa["citations"][0]["table_index"] in (1, 2)

    assert client.get(f"/api/audit/{paper_id}?generate=false").status_code == 404  # cache lookup never runs the LLM
    assert not any(c["name"] == "reproducibility-audit" for c in offline_models)
    first = client.get(f"/api/audit/{paper_id}")
    assert first.status_code == 200, first.text
    report = first.json()
    assert report["cached"] is False and len(report["categories"]) == 5
    assert report["grade"] in {"A+", "A", "B", "C", "D", "F"} and 0 <= report["overall_score"] <= 100
    assert "A100" in report["signals"]["accelerators"]
    assert "--learning_rate 3e-4" in report["recipe_command"]
    audit_prompt = next(c for c in offline_models if c["name"] == "reproducibility-audit")["user"]
    assert "| Learning rate | 3e-4 |" in audit_prompt  # tables feed the auditor

    assert client.get(f"/api/audit/{paper_id}").json()["cached"] is True
    assert client.post(f"/api/audit/{paper_id}/refresh").json()["cached"] is False

    export = client.get(f"/api/audit/{paper_id}/export")
    assert export.status_code == 200 and "attachment" in export.headers["content-disposition"]
    assert export.text.startswith("# Reproducibility Scorecard")

    assert client.get("/api/audit/missing-paper").status_code == 404
    client.delete(f"/api/papers/{paper_id}")
    assert client.get(f"/api/tables/{paper_id}").status_code == 404
