"""Table extractor (Stream B of the dual-stream parser).

Plain text extraction flattens 2D table grids into a 1D stream of numbers. This module finds
table regions with pdfplumber's layout analysis and keeps each table's structure in two forms:

1. Markdown, which goes into LLM prompts.
2. A JSON matrix (headers + rows + bbox), used for cell-level citations and the table viewer.

There are two detection strategies:
* Ruled tables: pdfplumber's default "lines" strategy (full vertical and horizontal rules).
* Booktabs tables (most arXiv / LaTeX papers): no vertical rules, just top/mid/bottom
  horizontal rules. These are found by locating a "Table N" caption, collecting the
  horizontal rules next to it and running a text-alignment extraction inside them.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber

from app.logger import logger
from app.observability import observe

# "Table 3: ...", "Tab. 2.", IEEE-style "TABLE IV" on its own line. In-text references such as
# "Table 2 shows ..." are not captions: mixed-case "Table N" must be followed by a separator or end of line.
_CAPTION = re.compile(
    r"^\s*(?:(?:Table|Tab\.)\s*(?:[0-9]{1,2}|[IVX]{1,5})\s*(?:[:.|]|$)|TABLE\s*(?:[0-9]{1,2}|[IVX]{1,5})(?![A-Za-z0-9]))"
)
_X_TOLERANCE = 1.5     # tighter than pdfplumber's default (3) so narrow word gaps keep their spaces
_COLUMN_GAP = 7.0      # min whitespace (pt) shared by all rows to count as a column separator
MAX_TABLES_PER_PAPER = 60
_MAX_CELL_CHARS = 200


@dataclass
class ExtractedTable:
    table_index: int
    page: int
    caption: str
    headers: list[str]
    rows: list[list[str]]
    markdown: str
    json_data: dict[str, Any] = field(default_factory=dict)

    def embedding_text(self, max_chars: int = 2000) -> str:
        """What gets embedded: caption, column names and the row labels/values."""
        body = "; ".join(" | ".join(c for c in row if c) for row in self.rows)
        return f"{self.caption}: Columns [{', '.join(h for h in self.headers if h)}]. Rows: {body}"[:max_chars]


# ---------------------------------------------------------------------------
# Cleaning and serialization
# ---------------------------------------------------------------------------
def _cell(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip() if value is not None else ""
    return text[:_MAX_CELL_CHARS]


def clean_matrix(raw: list[list[Any]]) -> list[list[str]]:
    """Normalize cells, pad ragged rows and drop rows/columns that are entirely empty."""
    matrix = [[_cell(c) for c in row] for row in raw if row]
    if not matrix:
        return []
    width = max(len(r) for r in matrix)
    matrix = [r + [""] * (width - len(r)) for r in matrix]
    matrix = [r for r in matrix if any(r)]
    if not matrix:
        return []
    keep = [j for j in range(width) if any(r[j] for r in matrix)]
    return [[r[j] for j in keep] for r in matrix]


def split_header(matrix: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    """First row is the header. A sparse first row (spanning group headers such as
    "GLUE" over "MNLI | QNLI") is forward-filled and merged with the row below it."""
    header, rows = matrix[0], matrix[1:]
    filled = sum(1 for c in header if c)
    if rows and len(header) > 2 and filled <= len(header) / 2 and sum(1 for c in rows[0] if c) > filled:
        top, carry = [], ""
        for i, c in enumerate(header):
            carry = c or (carry if i > 0 else "")
            top.append(carry)
        sub = rows[0]
        header = [f"{t} {s}".strip() if t and t != s else (s or t) for t, s in zip(top, sub)]
        rows = rows[1:]
    header = [h or f"Column {i + 1}" for i, h in enumerate(header)]
    return header, rows


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def to_markdown(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(_md_escape(h) for h in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines += ["| " + " | ".join(_md_escape(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _is_plausible(headers: list[str], rows: list[list[str]]) -> bool:
    """Reject false positives: single columns, header-only grids and mostly empty layouts."""
    if len(headers) < 2 or not rows:
        return False
    cells = [c for r in rows for c in r]
    fill = sum(1 for c in cells if c) / max(1, len(cells))
    # Text-alignment extraction of running prose yields long cells; real tables have short ones.
    avg_len = sum(len(c) for c in cells if c) / max(1, sum(1 for c in cells if c))
    return fill >= 0.35 and avg_len <= 60


# ---------------------------------------------------------------------------
# Captions and horizontal rules
# ---------------------------------------------------------------------------
def _caption_lines(page: Any) -> list[dict[str, Any]]:
    """Lines that start like a table caption, with their vertical position."""
    try:
        lines = page.extract_text_lines(return_chars=False, x_tolerance=_X_TOLERANCE)
    except Exception:
        return []
    captions = []
    for i, ln in enumerate(lines):
        match = _CAPTION.match(ln["text"])
        if not match:
            continue
        cap = {"text": ln["text"].strip(), "top": ln["top"], "bottom": ln["bottom"], "x0": ln["x0"], "x1": ln["x1"]}
        # IEEE style puts only "TABLE IV" on the caption line and the title on the next one.
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if len(ln["text"].strip()) <= match.end() + 1 and nxt and 0 <= nxt["top"] - ln["bottom"] <= 8:
            cap["text"] = f"{cap['text']}: {nxt['text'].strip()}"
            cap["bottom"] = nxt["bottom"]
            cap["x0"], cap["x1"] = min(cap["x0"], nxt["x0"]), max(cap["x1"], nxt["x1"])
        captions.append(cap)
    return captions


def _caption_near(captions: list[dict[str, Any]], bbox: tuple[float, ...]) -> str | None:
    """Caption directly above (within 60pt) or below (within 40pt) a table's bbox."""
    x0, top, x1, bottom = bbox
    best, best_gap = None, None
    for cap in captions:
        overlaps = cap["x0"] < x1 and cap["x1"] > x0
        if not overlaps:
            continue
        if 0 <= top - cap["bottom"] <= 60:
            gap = top - cap["bottom"]
        elif 0 <= cap["top"] - bottom <= 40:
            gap = cap["top"] - bottom
        else:
            continue
        if best_gap is None or gap < best_gap:
            best, best_gap = cap["text"], gap
    return best


def _horizontal_rules(page: Any) -> list[dict[str, float]]:
    """Horizontal rules wider than a quarter page, clustered by y (thin filled rects
    contribute two edges a fraction of a point apart)."""
    rules = []
    for e in page.edges:
        if e.get("orientation") != "h" or (e["x1"] - e["x0"]) < page.width * 0.25:
            continue
        y = (e["top"] + e["bottom"]) / 2
        for r in rules:
            if abs(r["y"] - y) <= 2 and r["x0"] < e["x1"] and r["x1"] > e["x0"]:
                r["x0"], r["x1"] = min(r["x0"], e["x0"]), max(r["x1"], e["x1"])
                break
        else:
            rules.append({"y": y, "x0": e["x0"], "x1": e["x1"]})
    return sorted(rules, key=lambda r: r["y"])


def _booktabs_region(
    cap: dict[str, Any], rules: list[dict[str, float]], captions: list[dict[str, Any]],
    page_width: float, page_height: float,
) -> tuple[float, ...] | None:
    """Bounding box of the rule group directly below or above a caption. A group never
    crosses another caption, so stacked tables are not merged."""
    cx0, cx1 = cap["x0"], cap["x1"]
    near = [r for r in rules if r["x0"] < cx1 + 50 and r["x1"] > cx0 - 50]
    next_cap = min((c["top"] for c in captions if c["top"] > cap["bottom"]), default=page_height)
    prev_cap = max((c["bottom"] for c in captions if c["bottom"] < cap["top"]), default=0.0)

    def group(candidates: list[dict[str, float]]) -> list[dict[str, float]]:
        out = [candidates[0]]
        for r in candidates[1:]:
            if abs(r["y"] - out[-1]["y"]) > 200:
                break
            out.append(r)
        return out

    below = [r for r in near if cap["bottom"] - 1 < r["y"] < next_cap]
    above = [r for r in reversed(near) if prev_cap < r["y"] < cap["top"] + 1]
    gap_below = below[0]["y"] - cap["bottom"] if below else None
    gap_above = cap["top"] - above[0]["y"] if above else None
    options = [(g, c) for g, c in ((gap_below, below), (gap_above, above)) if g is not None and g <= 30]
    if not options:
        return None
    grp = group(min(options, key=lambda o: o[0])[1])
    if len(grp) < 2:
        return None
    ys = [r["y"] for r in grp]
    top, bottom = max(0.0, min(ys) - 1), min(page_height, max(ys) + 1)
    if bottom - top < 12:
        return None
    return (max(0.0, min(r["x0"] for r in grp)), top, min(page_width, max(r["x1"] for r in grp)), bottom)


def words_to_matrix(words: list[dict[str, Any]], row_tolerance: float = 3.0) -> list[list[str]]:
    """Rebuild a grid from positioned words (for tables without vertical rules).

    Rows are clusters of words sharing a baseline. Column separators are vertical bands of
    whitespace at least _COLUMN_GAP wide that no body row puts text into. The header row is left out
    when finding separators because spanning group headers would otherwise hide them."""
    if not words:
        return []
    rows: list[list[dict[str, Any]]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if rows and abs(rows[-1][0]["top"] - w["top"]) <= row_tolerance:
            rows[-1].append(w)
        else:
            rows.append([w])
    basis = rows[1:] if len(rows) > 2 else rows
    intervals = sorted((w["x0"], w["x1"]) for row in basis for w in row)
    merged: list[list[float]] = []
    for x0, x1 in intervals:
        if merged and x0 - merged[-1][1] < _COLUMN_GAP:
            merged[-1][1] = max(merged[-1][1], x1)
        else:
            merged.append([x0, x1])
    cuts = [(a[1] + b[0]) / 2 for a, b in zip(merged, merged[1:])]

    matrix = []
    for row in rows:
        cells = [[] for _ in range(len(cuts) + 1)]
        for w in sorted(row, key=lambda w: w["x0"]):
            center = (w["x0"] + w["x1"]) / 2
            cells[sum(1 for c in cuts if center > c)].append(w["text"])
        matrix.append([" ".join(c) for c in cells])
    return matrix


def _overlaps(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def _page_tables(page: Any) -> list[tuple[tuple[float, ...], list[list[Any]], str | None]]:
    """(bbox, raw matrix, caption) for every table found on a page."""
    captions = _caption_lines(page)
    found: list[tuple[tuple[float, ...], list[list[Any]], str | None]] = []

    for t in page.find_tables():
        bbox = tuple(t.bbox)
        found.append((bbox, t.extract(), _caption_near(captions, bbox)))

    if captions:
        rules = _horizontal_rules(page)
        for cap in captions:
            if any(c == cap["text"] for _, _, c in found):
                continue
            region = _booktabs_region(cap, rules, captions, page.width, page.height)
            if not region or any(_overlaps(region, b) for b, _, _ in found):
                continue
            words = page.crop(region).extract_words(x_tolerance=_X_TOLERANCE, keep_blank_chars=False)
            raw = words_to_matrix(words)
            if raw:
                found.append((region, raw, cap["text"]))
    return sorted(found, key=lambda f: (f[0][1], f[0][0]))


@observe(name="extract-tables")
def extract_tables_from_pdf(pdf_path: Path) -> list[ExtractedTable]:
    extracted: list[ExtractedTable] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            try:
                page_tables = _page_tables(page)
            except Exception as e:  # one malformed page must not sink the whole document
                logger.warning(f"Table detection failed on page {page_num} of {pdf_path.name}: {e}")
                continue
            for bbox, raw, caption in page_tables:
                matrix = clean_matrix(raw or [])
                if len(matrix) < 2:
                    continue  # single-line noise or false positive
                headers, rows = split_header(matrix)
                if not _is_plausible(headers, rows):
                    continue
                index = len(extracted) + 1
                caption_text = (caption or f"Table {index} (page {page_num})")[:300]
                extracted.append(ExtractedTable(
                    table_index=index,
                    page=page_num,
                    caption=caption_text,
                    headers=headers,
                    rows=rows,
                    markdown=to_markdown(headers, rows),
                    json_data={"headers": headers, "rows": rows, "bbox": [round(v, 1) for v in bbox]},
                ))
                if len(extracted) >= MAX_TABLES_PER_PAPER:
                    return extracted
    return extracted
