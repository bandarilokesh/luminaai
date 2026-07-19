import re
from typing import List, Dict, Any

def validate_citations(text: str, citations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Checks the final text for citation markers (e.g. [1], [2]) and verifies 
    that they match the provided citation chunks.
    Returns validation metrics and optionally cleaned text if there are hallucinated citations.
    """
    # Find all citation markers in the text
    citation_markers = re.findall(r'\[(\d+)\]', text)
    
    # Convert to set of integers for unique cited chunk indices (assuming 1-based indexing in text)
    cited_indices = set(int(m) for m in citation_markers)
    
    valid_citations = []
    invalid_citations = []
    
    for idx in cited_indices:
        if 1 <= idx <= len(citations):
            valid_citations.append(idx)
        else:
            invalid_citations.append(idx)
            
    # Clean text: remove invalid citations
    cleaned_text = text
    for invalid_idx in invalid_citations:
        cleaned_text = cleaned_text.replace(f"[{invalid_idx}]", "")
        # Clean up empty brackets or double spaces if needed
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
    return {
        "original_text": text,
        "cleaned_text": cleaned_text,
        "valid_citations": valid_citations,
        "invalid_citations": invalid_citations,
        "citation_accuracy": len(valid_citations) / max(1, len(cited_indices))
    }
