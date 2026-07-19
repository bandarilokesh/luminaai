import uuid
from typing import List, Dict, Any

class HierarchicalChunker:
    """
    Chunks text hierarchically (Document -> Section -> Paragraph -> Sentence),
    maintaining parent-child relationships for intelligent retrieval.
    """
    
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        
    def chunk_document(self, doc_text: str, doc_id: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Takes raw document text (ideally pre-segmented by sections) and chunks it.
        For simplicity, this splits by double newlines (paragraphs) and then limits length.
        A full implementation would parse Markdown-like headers.
        """
        metadata = metadata or {}
        chunks = []
        
        # 1. Document Level Node
        doc_node_id = f"doc_{doc_id}"
        
        # Split into sections (naively by double newline for now, 
        # but in practice we use section_classifier.py)
        raw_sections = doc_text.split('\n\n')
        
        current_section_id = doc_node_id
        current_section_name = "General"
        
        for p_idx, para in enumerate(raw_sections):
            para = para.strip()
            if not para:
                continue
                
            # Naive header detection (ALL CAPS or short lines)
            if len(para) < 100 and (para.isupper() or para.istitle()):
                current_section_name = para
                current_section_id = f"sec_{doc_id}_{p_idx}"
                continue
                
            # If paragraph is too long, chunk it further
            if len(para) > self.chunk_size * 4: # approx char to token ratio
                sub_chunks = self._sliding_window(para)
                for sc_idx, sc in enumerate(sub_chunks):
                    chunks.append({
                        "chunk_id": str(uuid.uuid4()),
                        "paper_id": doc_id,
                        "level": 3, # 1=Doc, 2=Section, 3=Chunk
                        "parent_chunk_id": current_section_id,
                        "text_snippet": sc,
                        "section": current_section_name
                    })
            else:
                chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "paper_id": doc_id,
                    "level": 3,
                    "parent_chunk_id": current_section_id,
                    "text_snippet": para,
                    "section": current_section_name
                })
                
        return chunks
        
    def _sliding_window(self, text: str) -> List[str]:
        """Simple sliding window string chunker."""
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + self.chunk_size])
            chunks.append(chunk)
            i += self.chunk_size - self.overlap
        return chunks

hierarchical_chunker = HierarchicalChunker()
