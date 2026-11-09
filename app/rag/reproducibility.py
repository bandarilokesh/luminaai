"""Reproducibility & Leakage Audit Engine (Novelty 2).

Pipeline for one paper:
1. Evidence gathering: per-dimension semantic retrieval over the paper's chunks, plus the
   structured tables extracted at index time (hyperparameter / results tables are the ground truth).
2. Deterministic signals: regex scans of the full text for repository URLs, seeds, accelerators,
   variance reporting and significance tests, and (optionally) a live HEAD check of repository links.
3. LLM audit: one JSON call that fills a 5-dimension checklist against a fixed rubric.
4. Scoring: each dimension blends the LLM's rubric score with a score computed from the checklist
   item statuses, deterministic caps are applied, and the weighted sum gives ReproScore and grade.
5. Recipe synthesis: a Markdown reproduction guide (hardware, environment, CLI command, sweep warnings).
"""
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import settings
from app.observability import observe
from app.rag import llm
from app.rag.chunker import count_tokens
from app.rag.retriever import retrieve
from app.rag.vector_store import get_vector_store


class AuditError(ValueError):
    pass


@dataclass(frozen=True)
class Dimension:
    key: str
    name: str
    weight: float
    query: str
    checklist: tuple[str, ...]
    rubric: str


DIMENSIONS: tuple[Dimension, ...] = (
    Dimension(
        "hyperparameters", "Hyperparameter Completeness (HCI)", 0.25,
        "hyperparameters learning rate schedule warmup batch size optimizer Adam weight decay dropout epochs training steps random seed",
        ("Learning rate", "Learning-rate schedule / warmup", "Batch size (effective)", "Optimizer and its parameters",
         "Weight decay", "Dropout", "Gradient clipping", "Epochs or total training steps", "Random seeds"),
        "100 = all core hyperparameters with exact values; 70 = 70-90% reported, minor ones (e.g. warmup) omitted; "
        "40 = only learning rate and batch size; 10 = ambiguous or missing.",
    ),
    Dimension(
        "compute", "Compute & Environmental Footprint", 0.15,
        "GPU TPU hardware accelerator A100 V100 H100 number of GPUs training time hours GPU-hours distributed parallel carbon emissions energy",
        ("Accelerator model", "Number of devices", "Parallelization strategy", "Training wall-clock time / GPU-hours",
         "Energy or carbon estimate"),
        "100 = hardware model, device count, wall-clock hours and energy/carbon; 60 = hardware and training time, count or "
        "power omitted; 30 = vague (\"trained on GPUs\"); 0 = omitted.",
    ),
    Dimension(
        "data", "Dataset Lineage & Leakage Hygiene", 0.25,
        "dataset version download URL train validation test split sizes preprocessing tokenization filtering deduplication contamination overlap leakage",
        ("Dataset names and versions", "Dataset access (URL / DOI)", "Train / validation / test split sizes",
         "Preprocessing pipeline", "Contamination / train-test overlap check"),
        "100 = formal documentation with split sizes, contamination/deduplication analysis and public access; "
        "60 = public dataset but no contamination analysis; 30 = private data without distributions or leak checks; "
        "0 = undefined data source.",
    ),
    Dimension(
        "statistics", "Baseline Comparison & Statistical Rigor", 0.20,
        "standard deviation error bars confidence interval multiple runs seeds average over runs significance test p-value t-test baseline tuning",
        ("Number of runs / seeds", "Variance reporting (std, error bars, CI)", "Significance testing",
         "Baseline tuning parity"),
        "100 = multi-seed (N>=3) with std and significance tests (p<0.05); 60 = multi-seed with std but no hypothesis "
        "test; 25 = single-seed point estimates; 0 = anecdotal comparisons.",
    ),
    Dimension(
        "artifacts", "Artifact, Code & Checkpoint Availability", 0.15,
        "code available github repository open source released model weights checkpoints hugging face requirements docker environment",
        ("Public code repository", "Repository link resolves", "Model checkpoints / weights",
         "Environment specification (requirements, Docker, CUDA)"),
        "100 = public code + weights + reproducible environment file; 60 = code but weights private or environment "
        "unspecified; 20 = \"code will be released\" (unverified promise); 0 = nothing available.",
    ),
)
DIMENSION_BY_KEY = {d.key: d for d in DIMENSIONS}

GRADES = (
    (90.0, "A+", "Exemplary Reproducibility"),
    (80.0, "A", "Highly Reproducible"),
    (70.0, "B", "Moderately Reproducible"),
    (55.0, "C", "Limited Reproducibility"),
    (40.0, "D", "Poor Reproducibility"),
    (0.0, "F", "Non-Reproducible"),
)
STATUS_CREDIT = {"specified": 1.0, "partial": 0.5, "inferred": 0.4, "missing": 0.0}
RECIPE_ARGS = (
    "learning_rate", "lr_schedule", "warmup_steps", "batch_size", "epochs", "max_steps", "optimizer",
    "weight_decay", "dropout", "grad_clip", "max_seq_length", "seed",
)

AUDIT_SYSTEM_PROMPT = """You are Lumina's reproducibility auditor, acting as a strict NeurIPS/ICLR reproducibility reviewer.
Judge ONLY from the provided excerpts, tables and detected signals of one paper. Never invent values.
A parameter is "specified" only if an exact value is stated; "partial" if mentioned without full detail;
"inferred" if it can only be inferred indirectly (e.g. from a framework default); otherwise "missing".
Return valid JSON only."""

AUDIT_TEMPLATE = """Paper: {title}

=== EXCERPTS (numbered, with page) ===
{context}

=== EXTRACTED TABLES ===
{tables}

=== DETECTED SIGNALS (regex scan of the full text) ===
{signals}

=== TASK ===
Audit the paper's reproducibility across these five dimensions. For each dimension, score it 0-100 using its rubric and
return one item per checklist entry.

{dimensions}

Also list data-leakage risks (test data used for tuning/model selection, pretraining-evaluation overlap, temporal
leakage, duplicated samples across splits, preprocessing fitted on the full dataset) that the text suggests or fails
to rule out, and the critical parameters someone would have to guess to reproduce the main result.

Return JSON shaped exactly as:
{{"dimensions": {{"<dimension key>": {{"score": 0-100, "items": [{{"parameter": "...", "status": "specified|partial|inferred|missing",
"value": "exact value or null", "citation_page": page number or null, "risk_level": "low|medium|high", "note": "one sentence"}}]}}}},
"missing_critical_parameters": ["..."],
"potential_leakage_risks": ["..."],
"recipe": {{"model_name": "...", "parameter_count_billions": number or null, "framework": "... or null",
"python_version": "... or null", "cuda_version": "... or null", "libraries": ["..."], "hardware": "... or null",
"training_time": "... or null", "dataset": "... or null",
"arguments": {{{recipe_args}}}}}}}"""


# ---------------------------------------------------------------------------
# Deterministic signals
# ---------------------------------------------------------------------------
_URL = re.compile(r"https?://[^\s)\]}>,;\"']+", re.IGNORECASE)
_REPO_HOSTS = ("github.com", "gitlab.com", "huggingface.co", "bitbucket.org", "zenodo.org", "codeocean.com", "osf.io")
_SIGNALS = {
    "seed": r"\b(random\s+)?seeds?\b",
    "accelerator": r"\b(A100|H100|V100|A6000|A40|L40S?|P100|T4|RTX\s?\d{4}|TPU\s?v?\d|GPUs?)\b",
    "gpu_hours": r"\b(GPU[- ]hours?|TPU[- ]hours?|wall[- ]clock|hours on|days on)\b",
    "variance": r"(±|\\pm|standard deviation|std\.?|error bars?|confidence interval|\b95%\s*CI\b)",
    "multiple_runs": r"\b(averaged over|average of|mean of|across)\s+\d+\s+(runs|seeds|trials)\b|\b\d+\s+(random\s+)?(seeds|runs|trials)\b",
    "significance": r"(p\s*[<≤=]\s*0?\.\d+|p\s*\$?\\le\s*\$?\s*0?\.\d+|t-test|wilcoxon|permutation test|bootstrap|significan(t|ce))",
    "code_promise": r"\b(code|models?|data)\s+(will be|would be|is to be)\s+(made\s+)?(publicly\s+)?(available|released|open[- ]sourced)\b",
    "code_available": r"\b(code|implementation|models?|checkpoints?|weights)\s+(is|are)\s+(publicly\s+)?(available|released)\b",
    "environment": r"\b(requirements\.txt|environment\.ya?ml|pyproject\.toml|dockerfile|docker image|conda env|CUDA\s?\d+(\.\d+)?|PyTorch\s?\d|TensorFlow\s?\d|JAX)\b",
    "contamination": r"\b(contaminat\w*|de-?dup\w*|overlap (between|with)|n-gram overlap|leak\w*)\b",
    "carbon": r"\b(CO2|CO₂|carbon|kWh|energy consumption|emissions)\b",
}


def scan_signals(text: str) -> dict[str, Any]:
    """Cheap evidence that does not depend on the LLM."""
    found: dict[str, Any] = {}
    for name, pattern in _SIGNALS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        found[name] = len(matches)
    urls = []
    for url in _URL.findall(text):
        url = url.rstrip(".")
        if any(h in url.lower() for h in _REPO_HOSTS) and url not in urls:
            urls.append(url)
    found["repo_urls"] = urls[:8]
    accelerators = sorted({m.group(0).upper().replace(" ", "") for m in re.finditer(_SIGNALS["accelerator"], text, re.IGNORECASE)} - {"GPU", "GPUS"})
    found["accelerator_names"] = accelerators[:6]
    return found


def link_state(status_code: int) -> bool | None:
    """True = resolves, False = definitively dead (404, 410, ...), None = could not tell
    (server errors, rate limits and auth walls say nothing about whether the repository exists)."""
    if status_code < 400:
        return True
    if status_code < 500 and status_code not in (401, 403, 407, 408, 429):
        return False
    return None


def verify_links(urls: list[str], limit: int = 3, timeout: float = 6.0) -> list[dict[str, Any]]:
    """HEAD (falling back to GET) each repository URL. Only a definitive 4xx marks a link dead;
    timeouts and network errors leave it unverified rather than penalising the paper."""
    results = []
    if not settings.AUDIT_VERIFY_LINKS:
        return [{"url": u, "live": None, "status": "not checked"} for u in urls[:limit]]
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "LuminaAI-ReproAudit/1.0"}) as client:
        for url in urls[:limit]:
            try:
                res = client.head(url)
                if res.status_code in (403, 405, 501):
                    res = client.get(url)
                results.append({"url": url, "live": link_state(res.status_code), "status": str(res.status_code)})
            except httpx.HTTPError as e:
                results.append({"url": url, "live": None, "status": f"unreachable ({type(e).__name__})"})
    return results


def _signals_summary(signals: dict[str, Any], links: list[dict[str, Any]]) -> str:
    lines = [f"- {k}: {v} mention(s)" for k, v in signals.items() if isinstance(v, int)]
    lines.append(f"- accelerators named: {', '.join(signals['accelerator_names']) or 'none'}")
    lines.append(f"- repository URLs: {', '.join(signals['repo_urls']) or 'none found'}")
    for link in links:
        state = "live" if link["live"] else ("unverified" if link["live"] is None else "DEAD (not found)")
        lines.append(f"- link check {link['url']}: {state} ({link['status']})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Evidence gathering
# ---------------------------------------------------------------------------
_TABLE_HINTS = re.compile(r"hyper|parameter|setting|config|training|learning|batch|optimi|result|ablation|dataset|statistic|split", re.I)


def _select_tables(tables: list[dict[str, Any]], budget_tokens: int) -> tuple[str, list[dict[str, Any]]]:
    """Hyperparameter / dataset / results tables first, within a token budget."""
    ranked = sorted(tables, key=lambda t: (0 if _TABLE_HINTS.search(t["caption"] + " ".join(t.get("headers", []))) else 1, t["table_index"]))
    parts, used, total = [], [], 0
    for t in ranked:
        block = f"[Table {t['table_index']} | page {t['page']}] {t['caption']}\n{t['markdown']}"
        cost = count_tokens(block)
        if total + cost > budget_tokens:
            continue
        parts.append(block)
        used.append(t)
        total += cost
    return ("\n\n".join(parts) or "No structured tables were extracted from this paper."), used


def _gather_context(paper_id: str, budget_tokens: int) -> tuple[str, list[dict[str, Any]]]:
    """Top chunks per dimension, deduplicated and kept in reading order."""
    per_dim = max(2, 12 // len(DIMENSIONS))
    seen, selected = set(), []
    for dim in DIMENSIONS:
        for hit in retrieve(dim.query, [paper_id], top_k=per_dim + 1):
            if hit["chunk_index"] not in seen:
                seen.add(hit["chunk_index"])
                selected.append(hit)
    selected.sort(key=lambda c: c["chunk_index"])
    blocks, total = [], 0
    for chunk in selected:
        block = f"[p.{chunk['page']} | {chunk.get('section') or 'Unknown'}]\n{chunk['text'].strip()}"
        cost = count_tokens(block)
        if blocks and total + cost > budget_tokens:
            break
        blocks.append(block)
        total += cost
    return "\n\n---\n\n".join(blocks), selected


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def grade_for(score: float) -> tuple[str, str]:
    for threshold, grade, label in GRADES:
        if score >= threshold:
            return grade, label
    return "F", "Non-Reproducible"


def _clean_item(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not str(raw.get("parameter", "")).strip():
        return None
    status = str(raw.get("status", "missing")).lower().strip()
    if status not in STATUS_CREDIT:
        status = "missing"
    risk = str(raw.get("risk_level", "")).lower().strip()
    if risk not in ("low", "medium", "high"):
        risk = {"missing": "high", "partial": "medium", "inferred": "medium"}.get(status, "low")
    page = raw.get("citation_page")
    try:
        page = int(page) if page not in (None, "", "null") else None
    except (TypeError, ValueError):
        page = None
    value = raw.get("value")
    value = None if value in (None, "", "null", "None") else str(value)[:200]
    return {
        "parameter": str(raw["parameter"]).strip()[:120],
        "status": status,
        "value": value,
        "citation_page": page,
        "risk_level": risk,
        "note": str(raw.get("note") or "").strip()[:400] or "No further detail.",
    }


def score_dimension(llm_score: Any, items: list[dict[str, Any]]) -> float:
    """Blend the rubric score the LLM chose with the share of checklist items actually reported."""
    item_score = 100 * sum(STATUS_CREDIT[i["status"]] for i in items) / len(items) if items else None
    try:
        rubric = max(0.0, min(100.0, float(llm_score)))
    except (TypeError, ValueError):
        rubric = None
    if rubric is None and item_score is None:
        return 0.0
    if rubric is None:
        return round(item_score, 1)
    if item_score is None:
        return round(rubric, 1)
    return round(0.5 * rubric + 0.5 * item_score, 1)


def _apply_artifact_evidence(category: dict[str, Any], signals: dict[str, Any], links: list[dict[str, Any]]) -> None:
    """Deterministic guard rails for code availability: claims need a URL, and a dead URL is not code."""
    items = category["items"]
    if links:
        live = [link for link in links if link["live"]]
        checked = [link for link in links if link["live"] is not None]
        items.insert(0, {
            "parameter": "Repository link live check",
            "status": "specified" if live else ("missing" if checked else "partial"),
            "value": (live[0] if live else links[0])["url"],
            "citation_page": None,
            "risk_level": "low" if live else ("high" if checked else "medium"),
            "note": (f"{len(live)}/{len(checked)} repository link(s) resolved." if checked
                     else f"URL found in the text but could not be verified ({links[0]['status']})."),
        })
        if checked and not live:
            category["score"] = min(category["score"], 20.0)
    elif not signals["repo_urls"]:
        cap = 20.0 if signals.get("code_promise") else 10.0
        if category["score"] > cap:
            category["score"] = cap
            items.insert(0, {
                "parameter": "Repository URL",
                "status": "missing",
                "value": None,
                "citation_page": None,
                "risk_level": "high",
                "note": "No GitHub/GitLab/Hugging Face/Zenodo URL appears anywhere in the paper text.",
            })


# ---------------------------------------------------------------------------
# Recipe synthesis
# ---------------------------------------------------------------------------
def estimate_vram_gb(params_billions: float | None) -> dict[str, float] | None:
    """Rule of thumb: fp16 inference ~2 B/param; mixed-precision Adam training ~16 B/param + 20% activations."""
    try:
        p = float(params_billions)
    except (TypeError, ValueError):
        return None
    if p <= 0:
        return None
    return {"inference_gb": round(p * 2 * 1.2, 1), "training_gb": round(p * 16 * 1.2, 1)}


_PLAIN_ARG = re.compile(r"[\w.+-]+")


def _arg_value(value: Any) -> str | None:
    if value in (None, "", "null", "None", "unknown", "not specified"):
        return None
    return str(value).strip()[:80]


def synthesize_recipe(recipe: dict[str, Any], missing: list[str]) -> tuple[str, str, str]:
    """(markdown recipe, CLI command, hardware summary)."""
    recipe = recipe if isinstance(recipe, dict) else {}
    args = recipe.get("arguments") if isinstance(recipe.get("arguments"), dict) else {}
    model = _arg_value(recipe.get("model_name")) or "architecture_from_paper"
    dataset = _arg_value(recipe.get("dataset"))

    cmd = ["python train.py", f'  --model_name "{model}"']
    sweep = []
    for key in RECIPE_ARGS:
        value = _arg_value(args.get(key))
        if value is None:
            sweep.append(key)
            cmd.append(f"  --{key} <SWEEP>")
        else:
            shown = value if _PLAIN_ARG.fullmatch(value) else repr(value)
            cmd.append(f"  --{key} {shown}")
    cmd.append(f'  --dataset "{dataset}"' if dataset else "  --dataset <UNSPECIFIED>")
    command = " \\\n".join(cmd)

    vram = estimate_vram_gb(recipe.get("parameter_count_billions"))
    hardware = _arg_value(recipe.get("hardware")) or "Not reported"
    hardware_summary = hardware
    if vram:
        hardware_summary += f" | est. VRAM: ~{vram['inference_gb']} GB inference, ~{vram['training_gb']} GB full training"

    libs = [str(lib) for lib in recipe.get("libraries") or [] if lib][:12]
    env = [
        f"- **Framework:** {_arg_value(recipe.get('framework')) or 'Not reported'}",
        f"- **Python:** {_arg_value(recipe.get('python_version')) or 'Not reported (3.10+ recommended)'}",
        f"- **CUDA:** {_arg_value(recipe.get('cuda_version')) or 'Not reported'}",
        f"- **Libraries:** {', '.join(libs) if libs else 'Not reported'}",
    ]
    hw = [f"- **Reported hardware:** {hardware}",
          f"- **Reported training time:** {_arg_value(recipe.get('training_time')) or 'Not reported'}"]
    if vram:
        params = recipe.get("parameter_count_billions")
        hw.append(f"- **Estimated VRAM** ({params}B params): ~{vram['inference_gb']} GB for fp16 inference, "
                  f"~{vram['training_gb']} GB for full mixed-precision Adam training (before sharding).")
    warnings = [f"- `{k}` is not reported: sweep it or start from the framework default." for k in sweep]
    warnings += [f"- {m}" for m in missing if m]

    markdown = "\n".join([
        f"## Reproduction Recipe: {model}",
        "", "### 1. Target hardware", *hw,
        "", "### 2. Environment blueprint", *env,
        "", "### 3. Execution command", "```bash", command, "```",
        "", "### 4. Missing parameter warnings", *(warnings or ["- None: every core argument was reported."]),
    ])
    return markdown, command, hardware_summary


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _dimension_prompt() -> str:
    return "\n\n".join(
        f"- key \"{d.key}\": {d.name} (weight {int(d.weight * 100)}%)\n  Checklist: {'; '.join(d.checklist)}\n  Rubric: {d.rubric}"
        for d in DIMENSIONS
    )


@observe(name="reproducibility-audit")
def run_audit(paper_id: str, paper_title: str, tables: list[dict[str, Any]]) -> dict[str, Any]:
    chunks = get_vector_store().get_paper_chunks(paper_id)
    if not chunks:
        raise AuditError(f"Paper {paper_id} has no indexed chunks. Re-index it first.")
    full_text = "\n".join(c["text"] for c in chunks)
    table_text = "\n".join(t["markdown"] for t in tables)

    signals = scan_signals(full_text + "\n" + table_text)
    links = verify_links(signals["repo_urls"])

    budget = settings.AUDIT_CONTEXT_BUDGET
    tables_block, _ = _select_tables(tables, budget // 3)
    context, _ = _gather_context(paper_id, budget - count_tokens(tables_block))

    prompt = AUDIT_TEMPLATE.format(
        title=paper_title,
        context=context,
        tables=tables_block,
        signals=_signals_summary(signals, links),
        dimensions=_dimension_prompt(),
        recipe_args=", ".join(f'"{a}": "value or null"' for a in RECIPE_ARGS),
    )
    data = llm.generate_json(AUDIT_SYSTEM_PROMPT, prompt, name="reproducibility-audit", max_tokens=settings.AUDIT_MAX_TOKENS)
    if not isinstance(data, dict):
        raise AuditError("The model returned an unexpected audit format. Please retry.")
    return build_report(paper_id, paper_title, data, signals, links)


def build_report(
    paper_id: str, paper_title: str, data: dict[str, Any], signals: dict[str, Any], links: list[dict[str, Any]]
) -> dict[str, Any]:
    """Turn the LLM's raw audit JSON into a scored ReproducibilityReport dict."""
    raw_dims = data.get("dimensions") if isinstance(data.get("dimensions"), dict) else {}
    categories = []
    for dim in DIMENSIONS:
        raw = raw_dims.get(dim.key) or {}
        if not isinstance(raw, dict):
            raw = {}
        items = [i for i in (_clean_item(x) for x in raw.get("items") or []) if i]
        if not items:
            items = [{"parameter": c, "status": "missing", "value": None, "citation_page": None, "risk_level": "high",
                      "note": "The auditor found no evidence for this item."} for c in dim.checklist]
        category = {
            "key": dim.key,
            "category_name": dim.name,
            "weight": dim.weight,
            "score": score_dimension(raw.get("score"), items),
            "items": items,
        }
        if dim.key == "artifacts":
            _apply_artifact_evidence(category, signals, links)
        categories.append(category)

    overall = round(sum(c["score"] * c["weight"] for c in categories), 1)
    grade, classification = grade_for(overall)
    missing = [str(m).strip()[:200] for m in data.get("missing_critical_parameters") or [] if str(m).strip()][:15]
    leakage = [str(m).strip()[:300] for m in data.get("potential_leakage_risks") or [] if str(m).strip()][:10]
    recipe_md, command, hardware = synthesize_recipe(data.get("recipe") or {}, missing)

    return {
        "paper_id": paper_id,
        "paper_title": paper_title,
        "overall_score": overall,
        "grade": grade,
        "classification": classification,
        "categories": categories,
        "missing_critical_parameters": missing,
        "potential_leakage_risks": leakage,
        "reproduction_recipe": recipe_md,
        "recipe_command": command,
        "estimated_hardware": hardware,
        "signals": {
            "repo_urls": signals["repo_urls"],
            "link_checks": links,
            "accelerators": signals["accelerator_names"],
            "seed_mentions": signals["seed"],
            "variance_mentions": signals["variance"],
        },
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# Reviewer export
# ---------------------------------------------------------------------------
_STATUS_MARK = {"specified": "[x]", "partial": "[~]", "inferred": "[?]", "missing": "[ ]"}


def report_to_markdown(report: dict[str, Any]) -> str:
    """Peer-reviewer scorecard following the NeurIPS / ICLR / ACL reproducibility checklist layout."""
    lines = [
        f"# Reproducibility Scorecard: {report['paper_title']}",
        "",
        f"**ReproScore:** {report['overall_score']:.1f} / 100 &nbsp; **Grade:** {report['grade']} "
        f"({report.get('classification') or grade_for(report['overall_score'])[1]})",
        f"_Generated by Lumina AI on {report['created_at']}. Legend: [x] specified, [~] partial, [?] inferred, [ ] missing._",
        "",
        "## Score breakdown",
        "",
        "| Dimension | Weight | Score | Weighted |",
        "| --- | --- | --- | --- |",
    ]
    for c in report["categories"]:
        lines.append(f"| {c['category_name']} | {int(c['weight'] * 100)}% | {c['score']:.1f} | {c['score'] * c['weight']:.1f} |")
    for c in report["categories"]:
        lines += ["", f"## {c['category_name']} ({c['score']:.1f}/100)", ""]
        for item in c["items"]:
            value = f" = `{item['value']}`" if item.get("value") else ""
            page = f" (p. {item['citation_page']})" if item.get("citation_page") else ""
            lines.append(f"- {_STATUS_MARK.get(item['status'], '[ ]')} **{item['parameter']}**{value}{page}: "
                         f"{item['note']} _Risk: {item['risk_level']}._")
    lines += ["", "## Missing critical parameters", ""]
    lines += [f"- {m}" for m in report["missing_critical_parameters"]] or ["- None identified."]
    lines += ["", "## Potential data-leakage risks", ""]
    lines += [f"- {m}" for m in report["potential_leakage_risks"]] or ["- None identified."]
    lines += ["", "## Reviewer questions for the authors", ""]
    questions = [f"- Please report: {i['parameter']}." for c in report["categories"] for i in c["items"]
                 if i["status"] == "missing" and i["risk_level"] == "high"][:10]
    lines += questions or ["- No blocking questions."]
    lines += ["", report["reproduction_recipe"], ""]
    return "\n".join(lines)
