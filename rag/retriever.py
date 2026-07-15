import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from config.settings import settings
from utils.logger import logger
from rag.embeddings import embeddings_pipeline
from rag.vector_store import vector_store_manager
import torch
import numpy as np

# Lazy load CrossEncoder to minimize import overhead
_reranker_model = None

def get_reranker() -> CrossEncoder:
    """Lazy initialization of the Cross-Encoder re-ranker model."""
    global _reranker_model
    if _reranker_model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading Cross-Encoder re-ranker '{settings.RERANK_MODEL}' on device '{device}'...")
        os_env_cache = settings.CACHE_DIR / "huggingface"
        os_env_cache.mkdir(parents=True, exist_ok=True)
        _reranker_model = CrossEncoder(
            settings.RERANK_MODEL,
            device=device,
            cache_folder=str(os_env_cache)
        )
        logger.info("Re-ranker model loaded successfully.")
    return _reranker_model

def get_all_chunks_for_papers(paper_ids: List[str]) -> List[Dict[str, Any]]:
    """Retrieves all indexed text chunks and metadata for the selected papers."""
    chunks = []
    try:
        if settings.DEFAULT_VECTOR_DB == "faiss":
            # Read from FAISS metadata files
            for p_id in paper_ids:
                paper_dir = vector_store_manager.faiss_dir / p_id
                metadata_file = paper_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        paper_chunks = json.load(f)
                        chunks.extend(paper_chunks)
        else:
            # Read from ChromaDB
            collection = vector_store_manager._get_chroma_collection()
            where_filter = {}
            if len(paper_ids) == 1:
                where_filter = {"paper_id": paper_ids[0]}
            elif len(paper_ids) > 1:
                where_filter = {"paper_id": {"$in": paper_ids}}
                
            res = collection.get(
                where=where_filter if paper_ids else None,
                include=["documents", "metadatas"]
            )
            if res and res["ids"]:
                for idx in range(len(res["ids"])):
                    meta = res["metadatas"][idx].copy()
                    meta["chunk_id"] = res["ids"][idx]
                    meta["text"] = res["documents"][idx]
                    chunks.append(meta)
    except Exception as e:
        logger.error(f"Error fetching all chunks for papers: {str(e)}", exc_info=True)
        
    return chunks

import json # Import json for FAISS metadata file parsing

def tokenize_text(text: str) -> List[str]:
    """Simple alphanumeric tokenizer for BM25."""
    return re.findall(r'\b\w+\b', text.lower())

def retrieve_context(query: str, paper_ids: List[str], top_k: int = 10) -> List[Dict[str, Any]]:
    """Hybrid Retriever combining Dense Vector and Sparse Keyword search with Cross-Encoder re-ranking."""
    logger.info(f"Retrieving context for query: '{query}' | Target papers: {paper_ids}")
    
    if not paper_ids:
        return []
        
    # 1. Dense Vector Search
    query_vector = embeddings_pipeline.get_query_embedding(query)
    dense_results = vector_store_manager.search(paper_ids, query_vector, top_k=top_k * 2)
    
    # 2. Sparse Lexical Search (BM25)
    sparse_results = []
    all_chunks = get_all_chunks_for_papers(paper_ids)
    
    if all_chunks:
        # Tokenize corpus for BM25
        corpus = [tokenize_text(c["text"]) for c in all_chunks]
        bm25 = BM25Okapi(corpus)
        
        # Tokenize query and get scores
        tokenized_query = tokenize_text(query)
        bm25_scores = bm25.get_scores(tokenized_query)
        
        # Format BM25 results
        for idx, score in enumerate(bm25_scores):
            if score > 0.0:
                sparse_results.append({
                    "metadata": all_chunks[idx],
                    "score": float(score)
                })
        sparse_results.sort(key=lambda x: x["score"], reverse=True)
        sparse_results = sparse_results[:top_k * 2]

    # 3. Hybrid Fusion
    # Map both dense and sparse results into dictionaries indexed by chunk_id
    dense_dict = {r["metadata"]["chunk_id"]: r for r in dense_results}
    sparse_dict = {r["metadata"]["chunk_id"]: r for r in sparse_results}
    
    # Normalize dense scores to [0, 1]
    if dense_results:
        min_d = min(r["score"] for r in dense_results)
        max_d = max(r["score"] for r in dense_results)
        d_range = (max_d - min_d) + 1e-6
        for r in dense_results:
            r["norm_score"] = (r["score"] - min_d) / d_range
    
    # Normalize BM25 scores to [0, 1]
    if sparse_results:
        max_s = max(r["score"] for r in sparse_results)
        s_range = max_s + 1e-6
        for r in sparse_results:
            r["norm_score"] = r["score"] / s_range
            
    # Combine scores using alpha parameter
    combined_results = {}
    alpha = settings.HYBRID_ALPHA
    
    # Merge
    all_chunk_ids = set(dense_dict.keys()).union(sparse_dict.keys())
    for cid in all_chunk_ids:
        dense_item = dense_dict.get(cid)
        sparse_item = sparse_dict.get(cid)
        
        # Default metadata
        meta = dense_item["metadata"] if dense_item else sparse_item["metadata"]
        
        d_score = dense_item["norm_score"] if dense_item else 0.0
        s_score = sparse_item["norm_score"] if sparse_item else 0.0
        
        fused_score = alpha * d_score + (1.0 - alpha) * s_score
        
        combined_results[cid] = {
            "metadata": meta,
            "score": fused_score
        }
        
    merged_results = list(combined_results.values())
    merged_results.sort(key=lambda x: x["score"], reverse=True)
    merged_results = merged_results[:top_k * 2] # Keep top candidates for re-ranking

    # 4. Cross-Encoder Re-ranking
    if settings.USE_RERANKER and merged_results:
        try:
            reranker = get_reranker()
            
            # Format pairs for re-ranking: (query, text)
            pairs = [[query, r["metadata"]["text"]] for r in merged_results]
            
            # Get logits/scores
            rerank_scores = reranker.predict(pairs)
            
            # Update scores
            for r, score in zip(merged_results, rerank_scores):
                # Apply sigmoid-like mapping or keep raw score
                # Cross-Encoder scores are logits (unbounded). Higher is better.
                r["rerank_score"] = float(score)
                
            merged_results.sort(key=lambda x: x["rerank_score"], reverse=True)
            logger.info(f"Re-ranking completed. Top-1 score: {merged_results[0]['rerank_score'] if merged_results else 'N/A'}")
            
        except Exception as e:
            logger.error(f"Re-ranking failed, falling back to hybrid order: {str(e)}")
            
    # Return top-n results
    final_hits = merged_results[:settings.RERANK_TOP_N]
    
    # Return in standard citation format
    return [
        {
            "paper_name": h["metadata"]["paper_name"],
            "page": h["metadata"]["page"],
            "section": h["metadata"]["section"],
            "chunk_id": h["metadata"]["chunk_id"],
            "text_snippet": h["metadata"]["text"],
            "score": h.get("rerank_score") or h["score"]
        }
        for h in final_hits
    ]
