import re
import uuid
from typing import List, Dict, Any
from pathlib import Path
from utils.logger import logger
from rag.pdf_processor import extract_pdf_sections

def approximate_token_count(text: str) -> int:
    """Approximates the number of tokens in a text snippet (1 token ~= 4 chars)."""
    return len(text) // 4

def split_into_sentences(text: str) -> List[str]:
    """Helper to split paragraph text into sentences using simple regex."""
    # Split by periods, question marks or exclamation marks followed by spaces
    sentence_end = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s')
    sentences = sentence_end.split(text)
    return [s.strip() for s in sentences if s.strip()]

def chunk_document(paper_id: str, paper_name: str, full_text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Partitions document text into adaptive, heading-aware semantic chunks.
    
    Rather than hard-splitting at fixed sizes, it groups paragraphs and page splits,
    tracking section changes dynamically, and ensuring overlaps fall on sentence boundaries.
    """
    logger.info(f"Starting adaptive heading-aware chunking for paper: {paper_name}")
    
    # 1. Split full text into pages
    # Pages are separated by '--- PAGE SPLIT ---' in pdf_processor
    page_splits = full_text.split("\n\n--- PAGE SPLIT ---\n\n")
    
    # 2. Extract heading maps (with page boundaries)
    # Using the PDF path to re-extract if available, but we can also extract from text directly
    # To keep this clean, let's extract headings from page text using Regex
    headings = []
    section_regex = re.compile(
        r'^(?:[IVXLCDM]+\.?\s+|[0-9]+(?:\.[0-9]+)*\.?\s+|Abstract|Keywords|References|Introduction|Methodology|Results|Discussion|Conclusion)\b.*',
        re.IGNORECASE
    )
    
    # Compile a dictionary of page headings
    page_headings_map = {}
    for page_idx, page_text in enumerate(page_splits):
        page_num = page_idx + 1
        page_headings_map[page_num] = []
        lines = page_text.split("\n")
        for line in lines:
            line_s = line.strip()
            if len(line_s) < 100 and section_regex.match(line_s):
                page_headings_map[page_num].append(line_s)
                
    # 3. Create Chunks
    chunks = []
    chunk_index = 0
    
    active_section = "Abstract" if metadata.get("abstract") else "Introduction"
    active_heading = "Abstract" if metadata.get("abstract") else "1. Introduction"
    
    # Standard chunk token bounds (mapped to character counts)
    min_char_limit = 500 * 4   # 2000 chars
    max_char_limit = 900 * 4   # 3600 chars
    overlap_chars = 100 * 4    # 400 chars
    
    current_chunk_text = ""
    current_chunk_page = 1
    
    for page_idx, page_text in enumerate(page_splits):
        page_num = page_idx + 1
        
        # Split page into paragraphs
        paragraphs = page_text.split("\n\n")
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            # Check if this paragraph is actually a heading
            # If so, update the active heading/section
            is_heading = False
            for heading in page_headings_map.get(page_num, []):
                if para == heading or heading in para:
                    active_heading = heading
                    # Heuristically extract base section name
                    sec_clean = re.sub(r'^(?:[IVXLCDM]+\.?\s+|[0-9]+(?:\.[0-9]+)*\.?\s+)', '', heading).strip()
                    active_section = sec_clean
                    is_heading = True
                    break
                    
            # Check if adding this paragraph exceeds maximum limit
            if len(current_chunk_text) + len(para) > max_char_limit:
                # Flush current chunk
                if current_chunk_text:
                    tokens = approximate_token_count(current_chunk_text)
                    chunks.append({
                        "chunk_id": f"{paper_id}_chunk_{chunk_index}",
                        "paper_id": paper_id,
                        "paper_name": paper_name,
                        "text": current_chunk_text.strip(),
                        "page": current_chunk_page,
                        "section": active_section,
                        "heading": active_heading,
                        "tokens": tokens
                    })
                    chunk_index += 1
                    
                    # Create overlap text
                    # Grab the last `overlap_chars` from current chunk, aligned to sentence boundary
                    sentences = split_into_sentences(current_chunk_text)
                    overlap_acc = ""
                    for sent in reversed(sentences):
                        if len(overlap_acc) + len(sent) < overlap_chars:
                            overlap_acc = sent + " " + overlap_acc
                        else:
                            break
                    current_chunk_text = overlap_acc.strip() + " "
                else:
                    current_chunk_text = ""
                    
            # Add paragraph to chunk
            current_chunk_text += para + "\n\n"
            if len(current_chunk_text) == len(para) + 2: # newly started chunk
                current_chunk_page = page_num
                
    # Flush final remaining chunk
    if current_chunk_text.strip():
        tokens = approximate_token_count(current_chunk_text)
        chunks.append({
            "chunk_id": f"{paper_id}_chunk_{chunk_index}",
            "paper_id": paper_id,
            "paper_name": paper_name,
            "text": current_chunk_text.strip(),
            "page": current_chunk_page,
            "section": active_section,
            "heading": active_heading,
            "tokens": tokens
        })
        
    logger.info(f"Generated {len(chunks)} adaptive chunks for paper {paper_name}")
    return chunks
