import time
import json
import numpy as np
from typing import List, Dict, Any
from config.settings import settings
from utils.logger import logger
from rag.retriever import retrieve_context
from models.prompt_templates import build_qa_prompt
from models.llm_connector import query_llm

from rag.query_processor import expand_query
from rag.context_compressor import compress_context
from verification.claim_decomposer import decompose_into_claims
from verification.evidence_verifier import verify_all_claims
from verification.citation_validator import validate_citations
from verification.confidence_scorer import compute_confidence_score

def answer_question(
    paper_ids: List[str], 
    question: str, 
    model_name: str = None, 
    use_hybrid: bool = True, 
    use_reranker: bool = True
) -> Dict[str, Any]:
    """Retrieves context across selected papers and answers the question using local LLM, with full Phase 2 verification."""
    model_name = model_name or settings.DEFAULT_LLM_MODEL
    logger.info(f"Answering query: '{question}' using model: {model_name} over papers: {paper_ids}")
    
    # 1. Query Expansion
    expanded_queries = expand_query(question, model_name=model_name)
    all_queries = [question] + expanded_queries
    logger.info(f"Expanded queries: {expanded_queries}")
    
    # 2. Retrieve Context (using multiple queries)
    top_k = settings.TOP_K_DENSE
    if len(paper_ids) > 1:
        top_k = top_k * len(paper_ids)
        
    all_citations = []
    seen_chunk_ids = set()
    
    for q in all_queries:
        citations = retrieve_context(
            query=q,
            paper_ids=paper_ids,
            top_k=top_k
        )
        for c in citations:
            if c["chunk_id"] not in seen_chunk_ids:
                all_citations.append(c)
                seen_chunk_ids.add(c["chunk_id"])
                
    # Sort by score if available
    all_citations = sorted(all_citations, key=lambda x: x.get("score", 0.0), reverse=True)
    
    # 3. Context Compression
    compressed_citations = compress_context(all_citations, max_tokens=4000)
    
    if not compressed_citations:
        return {
            "answer": "I cannot find sufficient evidence in the uploaded paper(s) because no relevant context could be retrieved.",
            "citations": [],
            "confidence_score": 0.0,
            "faithfulness_score": 0.0,
            "retrieved_chunk_ids": [],
            "verification_json": {},
            "latency_sec": 0.0
        }
        
    # 4. Build QA prompt (Self-RAG included in template)
    system_prompt, user_prompt = build_qa_prompt(question, compressed_citations)
    
    # 5. Query LLM
    try:
        answer = query_llm(
            prompt=user_prompt,
            model_name=model_name,
            system_prompt=system_prompt
        )
    except Exception as e:
        logger.error(f"Failed to query LLM in qa_service: {str(e)}")
        answer = f"Error generating answer from local LLM: {str(e)}"
        
    # 6. Verification Pipeline
    evidence_texts = [c["text_snippet"] for c in compressed_citations]
    
    # a. Decompose claims
    claims = decompose_into_claims(answer, model_name=model_name)
    
    # b. Verify claims
    verification_results = verify_all_claims(claims, evidence_texts)
    
    # c. Validate citations
    citation_val = validate_citations(answer, compressed_citations)
    cleaned_answer = citation_val["cleaned_text"]
    
    # d. Compute Faithfulness & Confidence
    retrieval_scores = [c.get("score", 0.0) for c in compressed_citations]
    confidence_score = compute_confidence_score(
        retrieval_scores=retrieval_scores,
        verification_results=verification_results,
        citation_accuracy=citation_val["citation_accuracy"]
    )
    
    faithfulness_score = 0.0
    if verification_results:
        supported = sum(1 for res in verification_results if res["verification"]["status"] == "SUPPORTED")
        faithfulness_score = supported / len(verification_results)
        
    retrieved_ids = [c["chunk_id"] for c in compressed_citations]
    
    verification_json = {
        "claims": verification_results,
        "citation_validation": citation_val,
        "faithfulness": faithfulness_score
    }
    
    return {
        "answer": cleaned_answer,
        "citations": compressed_citations,
        "confidence_score": confidence_score,
        "faithfulness_score": round(faithfulness_score, 2),
        "verification_json": verification_json,
        "retrieved_chunk_ids": retrieved_ids
    }
