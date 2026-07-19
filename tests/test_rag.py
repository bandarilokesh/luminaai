import pytest
from rag.query_processor import query_processor
from rag.context_compressor import context_compressor
from verification.confidence_scorer import confidence_scorer

def test_multi_query_expansion(monkeypatch):
    # Mock LLM to return a simple JSON array
    def mock_query_llm(*args, **kwargs):
        return '["query 1", "query 2"]'
        
    monkeypatch.setattr("rag.query_processor.query_llm", mock_query_llm)
    
    queries = query_processor.expand_query("What is attention?", num_queries=2)
    assert len(queries) == 3
    assert queries[0] == "What is attention?"
    assert queries[1] == "query 1"

def test_context_compression():
    chunks = [
        {"chunk_id": "1", "text_snippet": "This is the first chunk."},
        {"chunk_id": "2", "text_snippet": "This is the second chunk."},
        {"chunk_id": "1", "text_snippet": "This is the first chunk."} # duplicate
    ]
    
    compressed = context_compressor.compress_and_filter(chunks, max_tokens=100)
    assert len(compressed) == 2
    
def test_confidence_scoring():
    score = confidence_scorer.calculate_confidence(
        retrieval_score=0.8,
        nli_entailment_ratio=1.0,
        citation_accuracy=1.0
    )
    assert score > 0.8
