import pytest
from agents.planner import planner

def test_planner_intent_classification(monkeypatch):
    # Mock LLM
    def mock_query_llm(prompt, *args, **kwargs):
        # The prompt template's own instructions mention "comparison" as an
        # intent option, so match on the quoted user query, not the full prompt.
        if "compare the methods" in prompt.lower():
            return '{"intent": "comparison"}'
        return '{"intent": "qa"}'
        
    monkeypatch.setattr("agents.planner.query_llm", mock_query_llm)
    
    intent1 = planner.determine_intent("Compare the methods of these two papers")
    assert intent1 == "comparison"
    
    intent2 = planner.determine_intent("What is the main finding?")
    assert intent2 == "qa"
