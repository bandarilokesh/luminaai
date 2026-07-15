import time
import re
from typing import List, Dict, Any, Tuple
from rouge_score import rouge_scorer
from sentence_transformers import SentenceTransformer
from config.settings import settings
from utils.logger import logger
from rag.embeddings import embeddings_pipeline
import numpy as np

class RAGEvaluator:
    """Evaluates RAG performance metrics locally including ROUGE, semantic similarity, and retrieval metrics."""
    def __init__(self):
        # Initialize ROUGE scorer
        self.rouge_scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)

    def calculate_rouge(self, reference: str, candidate: str) -> Dict[str, float]:
        """Calculates ROUGE-1, ROUGE-2, and ROUGE-L scores between a candidate response and reference text."""
        scores = self.rouge_scorer.score(reference, candidate)
        return {
            "rouge1_precision": float(scores["rouge1"].precision),
            "rouge1_recall": float(scores["rouge1"].recall),
            "rouge1_fmeasure": float(scores["rouge1"].fmeasure),
            "rouge2_fmeasure": float(scores["rouge2"].fmeasure),
            "rougeL_fmeasure": float(scores["rougeL"].fmeasure)
        }

    def calculate_semantic_similarity(self, reference: str, candidate: str, model_name: str = None) -> float:
        """Calculates the semantic similarity (embedding cosine similarity) as a fast local proxy for BERTScore."""
        try:
            emb_ref = embeddings_pipeline.get_query_embedding(reference, model_name)
            emb_cand = embeddings_pipeline.get_query_embedding(candidate, model_name)
            
            # Cosine similarity
            dot_product = np.dot(emb_ref, emb_cand)
            norm_ref = np.linalg.norm(emb_ref)
            norm_cand = np.linalg.norm(emb_cand)
            
            similarity = dot_product / (norm_ref * norm_cand + 1e-9)
            return float(similarity)
        except Exception as e:
            logger.error(f"Semantic similarity calculation failed: {str(e)}")
            return 0.0

    def calculate_retrieval_metrics(
        self, 
        retrieved_ids: List[str], 
        ground_truth_ids: List[str], 
        k: int = 5
    ) -> Dict[str, float]:
        """Calculates Precision@K, Recall@K, and MRR (Mean Reciprocal Rank) for the retriever."""
        k_retrieved = retrieved_ids[:k]
        
        # Calculate Precision@K
        relevant_retrieved = [cid for cid in k_retrieved if cid in ground_truth_ids]
        precision_at_k = len(relevant_retrieved) / k if k > 0 else 0.0
        
        # Calculate Recall@K
        recall_at_k = len(relevant_retrieved) / len(ground_truth_ids) if len(ground_truth_ids) > 0 else 0.0
        
        # Calculate Reciprocal Rank
        mrr = 0.0
        for rank, cid in enumerate(k_retrieved, 1):
            if cid in ground_truth_ids:
                mrr = 1.0 / rank
                break
                
        return {
            f"precision_at_{k}": precision_at_k,
            f"recall_at_{k}": recall_at_k,
            "reciprocal_rank": mrr
        }

    def evaluate_citation_accuracy(
        self, 
        answer: str, 
        retrieved_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyzes generated answer to evaluate citation accuracy and detect potential hallucinations.
        
        It parses inline citations format `[Paper Name, Page X, Section Y]` and verifies if
        they correspond to chunks that were actually retrieved.
        """
        # Regex to parse citations in answer
        citation_pattern = re.compile(r'\[([^,\n]+),\s*Page\s*(\d+),\s*Section\s*([^\]\n]+)\]', re.IGNORECASE)
        citations_found = citation_pattern.findall(answer)
        
        if not citations_found:
            return {
                "total_citations_cited": 0,
                "valid_citations_cited": 0,
                "citation_accuracy_rate": 1.0, # No citations to invalidate
                "hallucinated_citations": []
            }
            
        valid_count = 0
        hallucinated_citations = []
        
        # Compile retrieved signatures
        retrieved_signatures = set()
        for chunk in retrieved_chunks:
            # signature matches: (paper_name_lowercase, page_num)
            p_name = chunk["paper_name"].lower().strip()
            page = int(chunk["page"])
            retrieved_signatures.add((p_name, page))
            
        for paper, page_str, section in citations_found:
            p_name_cited = paper.lower().strip()
            page_cited = int(page_str)
            
            # Check matches
            # Allow partial matching on paper name
            match_found = False
            for ret_p_name, ret_page in retrieved_signatures:
                if (p_name_cited in ret_p_name or ret_p_name in p_name_cited) and page_cited == ret_page:
                    match_found = True
                    break
                    
            if match_found:
                valid_count += 1
            else:
                hallucinated_citations.append({
                    "paper": paper,
                    "page": page_cited,
                    "section": section
                })
                
        accuracy_rate = valid_count / len(citations_found)
        
        return {
            "total_citations_cited": len(citations_found),
            "valid_citations_cited": valid_count,
            "citation_accuracy_rate": float(accuracy_rate),
            "hallucinated_citations": hallucinated_citations
        }

# Singleton evaluator instance
evaluator = RAGEvaluator()
