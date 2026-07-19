import re
from typing import List, Dict, Any
from utils.logger import logger

class ReferenceParser:
    """
    Extracts structured references from a research paper text.
    """
    
    def extract_references(self, paper_text: str) -> List[Dict[str, str]]:
        """
        Attempts to locate the References section and parse individual references.
        """
        # Find references section
        # Look for "References", "Bibliography", "REFERENCES" usually towards the end of the text
        ref_match = re.search(r'\n(References|REFERENCES|Bibliography)\n', paper_text[-20000:])
        if not ref_match:
            return []
            
        ref_text = paper_text[-20000:][ref_match.end():]
        
        # Split by typical reference formats like "[1] Author", "1. Author"
        # Or standard IEEE/APA patterns. This is a heuristic.
        refs = re.split(r'\n(?=\[\d+\]\s|\d+\.\s)', ref_text)
        
        parsed_refs = []
        for i, ref in enumerate(refs):
            ref = ref.strip()
            if not ref:
                continue
                
            # Attempt to extract title/authors/venue naively
            # For a production system, use grobid or an LLM for parsing.
            parsed_refs.append({
                "raw": ref,
                "index": i + 1
            })
            
        return parsed_refs

reference_parser = ReferenceParser()
