"""Chunker: recursive chunking with overlap, sized in tokens.

Text is split on a hierarchy of separators (paragraphs -> lines -> sentences -> words) and a
section is only split further when it is still larger than CHUNK_SIZE. Adjacent pieces are then
merged back up to CHUNK_SIZE, carrying CHUNK_OVERLAP tokens between consecutive chunks.
"""
import math
import re
from dataclasses import dataclass

from app.config import settings
from app.rag.loader import LoadedDocument, detect_heading

SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def count_tokens(text: str) -> int:
    """Approximate token count (~4 characters per token for English text)."""
    return math.ceil(len(text) / 4)


@dataclass
class Chunk:
    chunk_index: int
    text: str
    page: int
    section: str


class RecursiveChunker:
    def __init__(self, chunk_size: int = settings.CHUNK_SIZE, chunk_overlap: int = settings.CHUNK_OVERLAP):
        if chunk_overlap >= chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> list[str]:
        return [c for c in self._split(text.strip(), SEPARATORS) if c.strip()]

    def _split(self, text: str, separators: list[str]) -> list[str]:
        if count_tokens(text) <= self.chunk_size:
            return [text]

        # Pick the first (largest) separator that occurs in the text.
        separator, remaining = separators[-1], []
        for i, sep in enumerate(separators):
            if sep == "" or sep in text:
                separator, remaining = sep, separators[i + 1:]
                break

        if separator:
            pieces = text.split(separator)
            # Keep the separator attached so sentences/paragraphs read naturally.
            pieces = [p + separator for p in pieces[:-1]] + [pieces[-1]]
        else:
            step = self.chunk_size * 4
            pieces = [text[i:i + step] for i in range(0, len(text), step)]

        chunks: list[str] = []
        buffer: list[str] = []
        for piece in pieces:
            if count_tokens(piece) > self.chunk_size:
                if buffer:
                    chunks.extend(self._merge(buffer))
                    buffer = []
                chunks.extend(self._split(piece, remaining) if remaining else [piece])
            else:
                buffer.append(piece)
        if buffer:
            chunks.extend(self._merge(buffer))
        return chunks

    def _merge(self, pieces: list[str]) -> list[str]:
        """Merge small pieces into chunks of at most chunk_size tokens with overlap."""
        chunks: list[str] = []
        window: list[str] = []
        total = 0
        for piece in pieces:
            size = count_tokens(piece)
            if window and total + size > self.chunk_size:
                chunks.append("".join(window).strip())
                # Drop pieces from the front until only the overlap remains.
                while window and (total > self.chunk_overlap or total + size > self.chunk_size):
                    total -= count_tokens(window.pop(0))
            window.append(piece)
            total += size
        if window:
            chunks.append("".join(window).strip())
        return chunks


def _headings(text: str) -> list[str]:
    return [h for h in (detect_heading(line) for line in text.splitlines()) if h]


def chunk_document(document: LoadedDocument, chunker: RecursiveChunker | None = None) -> list[Chunk]:
    """Split every page into chunks, keeping page number and section as metadata."""
    chunker = chunker or RecursiveChunker()
    chunks: list[Chunk] = []
    for page in document.pages:
        section = page.section
        for text in chunker.split_text(page.text):
            headings = _headings(text)
            chunks.append(Chunk(
                chunk_index=len(chunks),
                text=re.sub(r"\n{2,}", "\n\n", text),
                page=page.number,
                section=headings[0] if headings else section,
            ))
            if headings:
                section = headings[-1]
    return chunks
