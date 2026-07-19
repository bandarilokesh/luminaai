from typing import List, Dict, Any
import re

def compress_context(chunks: List[Dict[str, Any]], max_tokens: int = 4000) -> List[Dict[str, Any]]:
    """
    Compresses the context by:
    1. Deduplicating highly similar chunks (e.g., overlapping windows).
    2. Enforcing a strict token limit to prevent context window overflow.
    3. Truncating lowest-ranked chunks if necessary.
    """
    if not chunks:
        return []
        
    compressed_chunks = []
    seen_texts = set()
    current_tokens = 0
    
    for chunk in chunks:
        # Simple duplicate removal (exact match or near-exact)
        # In a more advanced version, we could use LLMLingua or sentence-transformers
        # to remove redundant sentences.
        text = chunk["text_snippet"]
        
        # Simple normalization for deduplication
        norm_text = re.sub(r'\s+', ' ', text.lower()).strip()
        
        if norm_text in seen_texts:
            continue
            
        seen_texts.add(norm_text)
        
        # Estimate tokens (approx 4 chars per token)
        est_tokens = len(text) // 4
        
        if current_tokens + est_tokens > max_tokens:
            # We reached the limit, stop adding chunks
            break
            
        compressed_chunks.append(chunk)
        current_tokens += est_tokens
        
    return compressed_chunks
