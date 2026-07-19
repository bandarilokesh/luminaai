import pytest
from rag.chunker import chunker

def test_chunking_hierarchy():
    text = "This is a simple text. It has sentences."
    chunks = chunker.chunk_text(text, paper_id="test1", section="Intro", level=2)
    assert len(chunks) > 0
    assert chunks[0]["level"] == 2
    assert chunks[0]["section"] == "Intro"
    assert chunks[0]["paper_id"] == "test1"
