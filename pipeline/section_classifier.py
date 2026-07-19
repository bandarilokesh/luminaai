import re
from typing import List, Dict, Any, Tuple
from utils.logger import logger

class SectionClassifier:
    """
    Enhanced section classifier for academic papers using regex and font heuristics.
    """
    def __init__(self):
        # Patterns covering standard formats (ACM, IEEE, Springer, Nature, arXiv)
        self.section_patterns = [
            # Standard numbered headings (e.g. 1. Introduction, 1.1 Background, I. INTRODUCTION)
            re.compile(r'^(?:[IVXLCDM]+|[0-9]+(?:\.[0-9]+)*)[\.\-\s]+(Abstract|Introduction|Background|Related Work|Method(?:ology)?|Experiments?|Results?|Discussion|Conclusion|References?|Acknowledge?ments)\b.*', re.IGNORECASE),
            # Plain headings without numbers
            re.compile(r'^(Abstract|Introduction|Background|Related Work|Method(?:ology)?|Experiments?|Results?|Discussion|Conclusion|References?|Acknowledge?ments)\b.*', re.IGNORECASE)
        ]
        
    def classify_sections(self, sorted_blocks: List[Tuple], page_num: int) -> List[Dict[str, Any]]:
        """
        Classifies blocks into sections based on heuristics.
        Returns a list of section boundaries.
        """
        sections = []
        
        for b in sorted_blocks:
            # text block format: (x0, y0, x1, y1, "text", block_no, block_type)
            if b[6] != 0:
                continue
                
            text = b[4].strip()
            # Split multiple lines inside block
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            
            for line in lines:
                # Basic heuristic: heading should be short
                if len(line) < 100:
                    for pattern in self.section_patterns:
                        match = pattern.match(line)
                        if match:
                            section_name = match.group(1).title()
                            sections.append({
                                "heading": line,
                                "section_name": section_name,
                                "page": page_num + 1,
                                "bbox": (b[0], b[1], b[2], b[3])
                            })
                            break # Found a match, don't check other patterns for this line
                            
        return sections
