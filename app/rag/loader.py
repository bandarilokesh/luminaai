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
    tables: list = field(default_factory=list)  # list[ExtractedTable], filled by the table stream

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


# ---------------------------------------------------------------------------
# Equation & LaTeX normalizer (Stream A)
# PDF text extraction turns math into loose unicode (θ, ∑, ≤, ℝ). We map those symbols back to
# LaTeX, wrap equation-like lines in $$...$$ and short inline symbol runs in $...$ so the LLM sees
# well-formed math and the frontend can render it with KaTeX.
# ---------------------------------------------------------------------------
_GREEK = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "ε": r"\epsilon", "ϵ": r"\epsilon",
    "ζ": r"\zeta", "η": r"\eta", "θ": r"\theta", "ϑ": r"\vartheta", "ι": r"\iota", "κ": r"\kappa",
    "λ": r"\lambda", "μ": r"\mu", "ν": r"\nu", "ξ": r"\xi", "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma",
    "τ": r"\tau", "υ": r"\upsilon", "φ": r"\phi", "ϕ": r"\phi", "χ": r"\chi", "ψ": r"\psi", "ω": r"\omega",
    "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda", "Ξ": r"\Xi", "Π": r"\Pi",
    "Σ": r"\Sigma", "Φ": r"\Phi", "Ψ": r"\Psi", "Ω": r"\Omega",
}
_OPERATORS = {
    "∑": r"\sum", "∏": r"\prod", "∫": r"\int", "∂": r"\partial", "∇": r"\nabla", "∈": r"\in",
    "∉": r"\notin", "⊂": r"\subset", "⊆": r"\subseteq", "⊃": r"\supset", "∪": r"\cup", "∩": r"\cap",
    "∀": r"\forall", "∃": r"\exists", "≤": r"\le", "≥": r"\ge", "≠": r"\neq", "≈": r"\approx",
    "≡": r"\equiv", "∝": r"\propto", "∞": r"\infty", "→": r"\to", "←": r"\leftarrow", "↦": r"\mapsto",
    "⇒": r"\Rightarrow", "⇔": r"\Leftrightarrow", "√": r"\sqrt", "‖": r"\|", "∥": r"\|", "⊤": r"\top",
    "⊙": r"\odot", "⊗": r"\otimes", "⊕": r"\oplus", "∼": r"\sim", "∘": r"\circ",
}
# Double-struck letters must be mapped before NFKC, which would fold ℝ into a plain "R".
_BLACKBOARD = {"ℝ": r"\mathbb{R}", "ℕ": r"\mathbb{N}", "ℤ": r"\mathbb{Z}", "ℚ": r"\mathbb{Q}",
               "ℂ": r"\mathbb{C}", "𝔼": r"\mathbb{E}", "ℙ": r"\mathbb{P}"}
# One private-use character per double-struck letter: survives NFKC and acts as a single symbol.
_BB_PLACEHOLDER = {char: chr(0xE010 + i) for i, char in enumerate(_BLACKBOARD)}
_SYMBOLS = {**_GREEK, **_OPERATORS, **{_BB_PLACEHOLDER[c]: latex for c, latex in _BLACKBOARD.items()}}
_SYMBOL_CLASS = "".join(re.escape(c) for c in _SYMBOLS)
_GREEK_CLASS = "".join(_GREEK)
_RELATION = re.compile(r"[=≤≥≈≠∝≡∈←→]")
_EQ_NUMBER = re.compile(r"\s*\((\d{1,3}[a-z]?)\)\s*$")
# A run of math symbols, allowing short glue (indices, brackets, operators) between them, plus a
# directly attached index such as the "1" in "β1".
_INLINE_RUN = re.compile(
    rf"[{_SYMBOL_CLASS}](?:[^\S\n]?[\w′'^_\-+*/()\[\],.]{{0,3}}[^\S\n]?[{_SYMBOL_CLASS}])*(?:\d{{1,2}}(?![\d.]))?"
)


def _protect_blackboard(text: str) -> str:
    for char, placeholder in _BB_PLACEHOLDER.items():
        text = text.replace(char, placeholder)
    return text


def _latexify(fragment: str) -> str:
    """Replace unicode math symbols with LaTeX commands and escape characters KaTeX treats specially."""
    fragment = re.sub(r"([%#&])", r"\\\1", fragment)
    fragment = re.sub(rf"([{_GREEK_CLASS}])(\d{{1,2}})(?![\d.])", r"\1_{\2}", fragment)  # β1 -> \beta_{1}
    out = []
    for char in fragment:
        latex = _SYMBOLS.get(char)
        out.append(latex + " " if latex else char)
    return re.sub(r"\s+", " ", "".join(out)).replace(" _{", "_{").strip()


def _strip_math_placeholders(text: str) -> str:
    """Placeholders left outside math become plain letters again (ℝ -> R)."""
    for char, placeholder in _BB_PLACEHOLDER.items():
        text = text.replace(placeholder, unicodedata.normalize("NFKC", char))
    return text


def is_display_equation(line: str) -> bool:
    """A short line dominated by math symbols, with a relation sign (=, ≤, ∈ ...), and at most one prose word."""
    stripped = line.strip()
    if not stripped or len(stripped) > 160 or "$" in stripped:
        return False
    symbols = len(re.findall(rf"[{_SYMBOL_CLASS}]", stripped))
    if symbols == 0 or not _RELATION.search(stripped):
        return False
    prose_words = len(re.findall(r"\b[a-zA-Z]{4,}\b", stripped))
    return prose_words <= 1 and (symbols >= 2 or "=" in stripped)


def normalize_math(text: str) -> str:
    """Wrap equation lines in $$...$$ (with \\tag for "(3)" numbering) and inline symbol runs in $...$."""
    lines = []
    for line in text.split("\n"):
        if is_display_equation(line):
            body, tag = line.strip(), ""
            number = _EQ_NUMBER.search(body)
            if number:
                body, tag = body[: number.start()], rf" \tag{{{number.group(1)}}}"
            lines.append(f"$$ {_latexify(body)}{tag} $$")
        elif "$" in line:
            lines.append(line)  # already contains math or currency; leave it alone
        else:
            lines.append(_INLINE_RUN.sub(lambda m: f"${_latexify(m.group(0))}$", line))
    return _strip_math_placeholders("\n".join(lines))


def _normalize(text: str) -> str:
    """Normalize encoding, fix hyphenated line breaks, collapse extra spaces/blank lines and
    convert unicode math into LaTeX."""
    text = unicodedata.normalize("NFKC", _protect_blackboard(text)).replace("­", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return normalize_math(text.strip())


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
