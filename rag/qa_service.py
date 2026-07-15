import time
from typing import List, Dict, Any
from config.settings import settings
from utils.logger import logger
from rag.retriever import retrieve_context
from models.prompt_templates import build_qa_prompt
from models.llm_connector import query_llm

def answer_question(
    paper_ids: List[str], 
    question: str, 
    model_name: str = None, 
    use_hybrid: bool = True, 
    use_reranker: bool = True
) -> Dict[str, Any]:
    """Retrieves context across selected papers and answers the question using local LLM."""
    model_name = model_name or settings.DEFAULT_LLM_MODEL
    logger.info(f"Answering query: '{question}' using model: {model_name} over papers: {paper_ids}")
    
    # 1. Retrieve context
    # Adjust retrieve limits based on whether we query a single paper or multiple papers
    top_k = settings.TOP_K_DENSE
    if len(paper_ids) > 1:
        top_k = top_k * len(paper_ids) # Retrieve more chunks if querying across multiple papers
        
    citations = retrieve_context(
        query=question,
        paper_ids=paper_ids,
        top_k=top_k
    )
    
    if not citations:
        return {
            "answer": "I cannot find sufficient evidence in the uploaded paper(s) because no relevant context could be retrieved.",
            "citations": [],
            "confidence_score": 0.0,
            "retrieved_chunk_ids": [],
            "latency_sec": 0.0
        }
        
    # 2. Build QA prompt
    system_prompt, user_prompt = build_qa_prompt(question, citations)
    
    # 3. Query Local LLM
    try:
        answer = query_llm(
            prompt=user_prompt,
            model_name=model_name,
            system_prompt=system_prompt
        )
    except Exception as e:
        logger.error(f"Failed to query LLM in qa_service: {str(e)}")
        answer = f"Error generating answer from local LLM: {str(e)}"
        
    # 4. Compute Confidence Score
    # Simple heuristic: average of top-n retrieval scores.
    # If LLM reports missing evidence, set confidence score to 0.0.
    confidence_score = 0.0
    if "I cannot find sufficient evidence" not in answer:
        scores = [c["score"] for c in citations if "score" in c]
        if scores:
            # Map re-ranker logits or cosine similarity to a nice percentage
            # Cosine similarity is usually 0.3 - 0.8
            avg_score = sum(scores) / len(scores)
            
            # Simple normalization to [0,1]
            if settings.USE_RERANKER:
                # Logits can be negative or positive (e.g. -5 to 10)
                # Map logit to sigmoid
                confidence_score = float(1.0 / (1.0 + np.exp(-avg_score)))
            else:
                confidence_score = float(max(0.0, min(1.0, (avg_score + 1.0) / 2.0)))
        else:
            confidence_score = 0.70 # Default fallback
            
    retrieved_ids = [c["chunk_id"] for c in citations]
    
    return {
        "answer": answer,
        "citations": citations,
        "confidence_score": round(confidence_score, 2),
        "retrieved_chunk_ids": retrieved_ids
    }
import numpy as np # Import numpy for sigmoid logit mapping
