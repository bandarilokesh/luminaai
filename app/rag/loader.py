"""Loader: parse a PDF, clean the text and collect metadata for each page."""
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from app.observability import observe

# Headings such as "1 Introduction", "3.2. Methods", "ABSTRACT", "Related Work"
_KNOWN_SECTIONS = (
    "abstract", "introduction", "background", "related work", "literature review",
    "method", "methods", "methodology", "approach", "model", "experiments", "experimental setup",
    "evaluation", "results", "discussion", "analysis", "limitations", "future work",
    "conclusion", "conclusions", "references", "acknowledgements", "acknowledgments", "appendix",
)
_NUMBERED_HEADING = re.compile(r"^(\d{1,2}(\.\d{1,2})*\.?|[IVX]{1,4}\.)\s+([A-Z][A-Za-z\-,:& ]{2,60})$")


@dataclass
class Page:
    number: int
    text: str
    section: str  # section in effect at the start of the page


@dataclass
class LoadedDocument:
    title: str
    authors: str
    abstract: str
    page_count: int
    pages: list[Page] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


def _normalize(text: str) -> str:
    """Normalize encoding, fix hyphenated line breaks and collapse extra spaces/blank lines."""
    text = unicodedata.normalize("NFKC", text).replace("­", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _repeated_lines(raw_pages: list[str]) -> set[str]:
    """Lines that appear on most pages (running headers/footers)."""
    if len(raw_pages) < 3:
        return set()
    counts = Counter()
    for page in raw_pages:
        lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
        counts.update(set(lines[:3] + lines[-3:]))
    return {line for line, n in counts.items() if n >= max(3, len(raw_pages) // 2)}


def clean_page(raw: str, noise: set[str]) -> str:
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped in noise:
            continue
        if re.fullmatch(r"(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?", stripped, re.IGNORECASE):
            continue  # bare page numbers
        lines.append(line)
    return _normalize("\n".join(lines))


def detect_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > 70:
        return None
    match = _NUMBERED_HEADING.match(stripped)
    if match:
        return match.group(3).strip().title()
    lowered = stripped.lower().rstrip(":.")
    if lowered in _KNOWN_SECTIONS:
        return lowered.title()
    return None


def _extract_title(doc: pymupdf.Document, first_page: str) -> str:
    meta_title = (doc.metadata or {}).get("title", "").strip()
    if meta_title and len(meta_title) > 5 and not meta_title.lower().startswith(("microsoft word", "untitled")):
        return meta_title
    # Fall back to the largest text on the first page.
    try:
        spans = []
        for block in doc[0].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip():
                        spans.append((span["size"], span["text"].strip()))
        if spans:
            max_size = max(s for s, _ in spans)
            title = " ".join(t for s, t in spans if s >= max_size - 0.5)
            if 5 < len(title) < 250:
                return title
    except Exception:
        pass
    for line in first_page.splitlines():
        if 5 < len(line.strip()) < 200:
            return line.strip()
    return ""


def _extract_abstract(text: str) -> str:
    match = re.search(
        r"\babstract\b[\s.:\-—]*(.+?)(?=\n\s*(?:\d{1,2}\.?\s*|I\.\s*)?(?:introduction|keywords|index terms)\b)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    abstract = match.group(1) if match else ""
    return re.sub(r"\s+", " ", abstract).strip()[:3000]


@observe(name="load-pdf")
def load_pdf(file_path: Path) -> LoadedDocument:
    """Load a PDF into cleaned pages with section metadata."""
    with pymupdf.open(file_path) as doc:
        raw_pages = [page.get_text("text") for page in doc]
        noise = _repeated_lines(raw_pages)
        cleaned = [clean_page(raw, noise) for raw in raw_pages]

        pages: list[Page] = []
        section = "Front Matter"
        for number, text in enumerate(cleaned, start=1):
            if text:
                pages.append(Page(number=number, text=text, section=section))
            for line in text.splitlines():
                section = detect_heading(line) or section

        first_page = cleaned[0] if cleaned else ""
        title = _extract_title(doc, first_page) or file_path.stem
        authors = (doc.metadata or {}).get("author", "").strip()
        abstract = _extract_abstract("\n".join(cleaned[:2]))

        return LoadedDocument(
            title=title,
            authors=authors,
            abstract=abstract,
            page_count=len(raw_pages),
            pages=pages,
        )
