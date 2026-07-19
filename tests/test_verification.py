import pytest
from verification.hallucination_detector import hallucination_detector
from verification.citation_validator import citation_validator
from verification.evidence_verifier import evidence_verifier

def test_evidence_verification(monkeypatch):
    def mock_query_llm(*args, **kwargs):
        return '{"supported": true, "reason": "test"}'
    monkeypatch.setattr("verification.evidence_verifier.query_llm", mock_query_llm)
    
    result = evidence_verifier.verify_claim("Test claim", "Test context")
    assert result["supported"] is True

def test_citation_validation():
    # Simple test for citation regex extraction
    text = "This is a statement [1][2]."
    citations = citation_validator.extract_citations(text)
    assert len(citations) == 2
    assert "1" in citations
    assert "2" in citations
