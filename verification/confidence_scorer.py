from typing import List, Dict, Any

def compute_confidence_score(
    retrieval_scores: List[float],
    verification_results: List[Dict[str, Any]],
    citation_accuracy: float
) -> float:
    """
    Computes a robust confidence score combining multiple signals:
    1. Retrieval relevance (how good the context was)
    2. Faithfulness (how many claims are supported by context)
    3. Citation accuracy (how many citations point to valid chunks)
    """
    
    # 1. Retrieval Signal (0.0 to 1.0)
    retrieval_signal = 0.0
    if retrieval_scores:
        avg_score = sum(retrieval_scores) / len(retrieval_scores)
        # Assuming scores might be cross-encoder logits or cosine similarities
        # If logits, map them to 0-1, but for safety let's normalize simply
        retrieval_signal = max(0.0, min(1.0, (avg_score + 10) / 20)) # basic normalization for logits
        
    # 2. Faithfulness Signal (0.0 to 1.0)
    faithfulness_signal = 1.0
    if verification_results:
        supported = sum(1 for res in verification_results if res["verification"]["status"] == "SUPPORTED")
        faithfulness_signal = supported / len(verification_results)
        
    # 3. Combine signals with weights
    w_retrieval = 0.3
    w_faithfulness = 0.5
    w_citation = 0.2
    
    final_score = (
        (retrieval_signal * w_retrieval) + 
        (faithfulness_signal * w_faithfulness) + 
        (citation_accuracy * w_citation)
    )
    
    return round(final_score, 2)
