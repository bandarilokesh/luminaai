import pytest
from evaluation.evaluator import evaluator

def test_rouge_scorer():
    ref = "The quick brown fox jumps over the lazy dog"
    cand = "The brown fox jumps over a lazy dog"
    
    scores = evaluator.calculate_rouge(ref, cand)
    
    assert scores["rouge1_fmeasure"] > 0.7
    assert scores["rougeL_fmeasure"] > 0.7
    assert "rouge2_fmeasure" in scores

def test_retrieval_metrics():
    retrieved = ["chunk_0", "chunk_1", "chunk_2", "chunk_3", "chunk_4"]
    ground_truth = ["chunk_1", "chunk_4", "chunk_9"]
    
    metrics = evaluator.calculate_retrieval_metrics(retrieved, ground_truth, k=3)
    
    # In top 3: chunk_1 is present. chunk_4 and chunk_9 are not in top 3.
    # Precision@3 = 1 / 3 = 0.333
    # Recall@3 = 1 / 3 = 0.333
    # MRR: chunk_1 is rank 2. Reciprocal rank = 1/2 = 0.5
    
    assert abs(metrics["precision_at_3"] - 0.333) < 0.01
    assert abs(metrics["recall_at_3"] - 0.333) < 0.01
    assert metrics["reciprocal_rank"] == 0.5

def test_evaluate_citation_accuracy():
    # Answer with correct and hallucinated citations
    answer = (
        "According to the experiments [Paper_A.pdf, Page 2, Section Results], the accuracy was 95%. "
        "However, other models had limitations [Paper_B.pdf, Page 10, Section Limitations]."
    )
    
    # Retrieved chunks context
    retrieved_chunks = [
        {"paper_name": "Paper_A.pdf", "page": 2},
        {"paper_name": "Paper_B.pdf", "page": 5} # Cites page 10, but we retrieved page 5 -> mismatch!
    ]
    
    results = evaluator.evaluate_citation_accuracy(answer, retrieved_chunks)
    
    assert results["total_citations_cited"] == 2
    assert results["valid_citations_cited"] == 1
    assert results["citation_accuracy_rate"] == 0.5
    assert len(results["hallucinated_citations"]) == 1
    assert results["hallucinated_citations"][0]["paper"] == "Paper_B.pdf"
    assert results["hallucinated_citations"][0]["page"] == 10
