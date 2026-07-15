import re
from pathlib import Path
from typing import Dict, Any, Tuple, List
import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
import io
from utils.logger import logger

# Try loading pytesseract, handle import/binary absence gracefully
PYTESSERACT_AVAILABLE = False
try:
    import pytesseract
    # Test if tesseract is accessible, otherwise mark unavailable
    pytesseract.get_tesseract_version()
    PYTESSERACT_AVAILABLE = True
except Exception:
    logger.warning("Pytesseract OCR binary/module is not configured or installed. Scanned PDF fallback will run without OCR.")

def clean_extracted_text(text: str) -> str:
    """Cleans up common PDF extraction noise such as double spaces, bad hyphens, footers."""
    if not text:
        return ""
    # Normalize whitespaces
    text = re.sub(r'[ \t]+', ' ', text)
    # Remove hyphenated line splits (e.g. "deve- \n lopment" -> "development")
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    # Remove excessive consecutive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def sort_blocks_by_layout(blocks: List[Tuple]) -> List[Tuple]:
    """Sort text blocks extracted by PyMuPDF to follow reading order (two-column layout aware).
    Each block tuple: (x0, y0, x1, y1, "text", block_no, block_type)
    """
    # Sort vertically first, then split into columns if they overlap horizontally
    # A standard 2-column layout splits page vertically. We look at x coordinates.
    # Standard page width is typically 500-600 points. We check mid point.
    if not blocks:
        return []
        
    # Filter out image blocks, keep only text blocks
    text_blocks = [b for b in blocks if b[6] == 0]
    
    # Heuristic layout sort
    # If the page has two columns, we want to read column 1 top-to-bottom, then column 2 top-to-bottom.
    # Let's find midpoint of x coordinates
    x_coords = [b[0] for b in text_blocks] + [b[2] for b in text_blocks]
    if not x_coords:
        return text_blocks
        
    min_x = min(x_coords)
    max_x = max(x_coords)
    mid_x = min_x + (max_x - min_x) / 2
    
    col1 = []
    col2 = []
    
    for b in text_blocks:
        # If the block is entirely to the left of midpoint, it's col 1
        # If it is entirely to the right, it's col 2
        # If it spans across the midpoint (like title, abstract), we classify it based on centers
        center_x = (b[0] + b[2]) / 2
        width = b[2] - b[0]
        page_width = max_x - min_x
        
        # If block spans more than 65% of the page width, treat as span (title/abstract) and put in col1 for order
        if width > 0.65 * page_width:
            col1.append(b)
        elif center_x < mid_x:
            col1.append(b)
        else:
            col2.append(b)
            
    # Sort each column by y-coordinate (top-to-bottom)
    col1.sort(key=lambda x: x[1])
    col2.sort(key=lambda x: x[1])
    
    # Return merged: left column blocks, then right column blocks
    return col1 + col2

def perform_ocr_on_page(page: fitz.Page) -> str:
    """Renders a PDF page as image and extracts text using pytesseract OCR."""
    if not PYTESSERACT_AVAILABLE:
        logger.warning(f"OCR requested for page {page.number} but Tesseract is not configured.")
        return ""
    try:
        logger.info(f"Running OCR on page {page.number}...")
        # Render page to PNG bytes
        pix = page.get_pixmap(dpi=150)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        # Run OCR
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        return ""

def extract_pdf_data(file_path: Path) -> Tuple[Dict[str, Any], str]:
    """Reads PDF and extracts cleaned layout-aware text, sections, and metadata."""
    logger.info(f"Opening PDF for processing: {file_path}")
    
    metadata = {
        "title": file_path.stem.replace("_", " ").title(),
        "authors": "Unknown",
        "abstract": "",
        "keywords": "",
        "doi": "",
        "publication_year": None
    }
    
    full_text_list = []
    
    # 1. Open with PyMuPDF for layout and text extraction
    doc = fitz.open(str(file_path))
    total_pages = len(doc)
    logger.info(f"PDF contains {total_pages} pages.")
    
    # Keep track of page text blocks
    for page_num in range(total_pages):
        page = doc[page_num]
        
        # Get blocks
        blocks = page.get_text("blocks")
        sorted_blocks = sort_blocks_by_layout(blocks)
        
        page_text = ""
        for b in sorted_blocks:
            page_text += b[4] + "\n"
            
        page_text = clean_extracted_text(page_text)
        
        # OCR Fallback for scanned/empty pages
        if len(page_text.strip()) < 50 and PYTESSERACT_AVAILABLE:
            ocr_text = perform_ocr_on_page(page)
            if ocr_text:
                page_text = clean_extracted_text(ocr_text)
                
        full_text_list.append(page_text)
        
    full_text = "\n\n--- PAGE SPLIT ---\n\n".join(full_text_list)
    
    # 2. Extract Metadata details (Heuristics)
    first_page_text = full_text_list[0] if full_text_list else ""
    
    # Extract DOI via regex
    doi_match = re.search(r'\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b', first_page_text, re.IGNORECASE)
    if doi_match:
        metadata["doi"] = doi_match.group(1)
        
    # Extract Publication Year via regex (look for 19xx or 20xx in context of dates or metadata)
    year_matches = re.findall(r'\b(19\d{2}|20\d{2})\b', first_page_text)
    # Filter years (e.g. must be <= current year)
    current_year = datetime.now().year if 'datetime' in globals() else 2026
    valid_years = [int(y) for y in year_matches if 1950 <= int(y) <= current_year]
    if valid_years:
        # Heuristically, the publication year is often the first valid year or appears multiple times. Let's take the first.
        metadata["publication_year"] = valid_years[0]

    # Extract Abstract
    # Look for Abstract header and grab everything until Introduction or next heading
    abstract_patterns = [
        r'(?:ABSTRACT|Abstract)\b:?[\s\n]*(.*?)(?:\bINTRODUCTION\b|\bIntroduction\b|\b1\.\s+Introduction\b|\bI\.\s+Introduction\b|2\.\s+|\bKeywords\b|\bKey\s+words\b)',
        r'(?:ABSTRACT|Abstract)\b:?[\s\n]*(.*?)(?:\n\n\n|\r|\Z)'
    ]
    for pattern in abstract_patterns:
        abstract_match = re.search(pattern, first_page_text, re.DOTALL | re.IGNORECASE)
        if abstract_match:
            abstract_text = abstract_match.group(1).strip()
            if len(abstract_text) > 50:
                metadata["abstract"] = clean_extracted_text(abstract_text)
                break

    # Extract Keywords
    keywords_match = re.search(r'(?:Keywords|Key\s+words|Key-words)\b:?[\s\n]*(.*?)(?:\n|\bIntroduction\b|\bAbstract\b|\Z)', first_page_text, re.IGNORECASE)
    if keywords_match:
        metadata["keywords"] = clean_extracted_text(keywords_match.group(1))

    # Extract Title & Authors (Heuristics using pdfplumber for font metadata if possible, otherwise first few blocks of PyMuPDF)
    # PyMuPDF block extraction: Title is usually the first large block (highest font size).
    try:
        title_extracted = False
        authors_extracted = False
        
        # Let's inspect character sizes in first page
        page_dict = doc[0].get_text("dict")
        blocks = page_dict.get("blocks", [])
        
        spans = []
        for b in blocks:
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        spans.append(span)
                        
        if spans:
            # Sort spans by font size descending
            spans.sort(key=lambda s: s["size"], reverse=True)
            
            # The span with maximum font size is likely the title (or part of it)
            max_size = spans[0]["size"]
            title_spans = [s for s in spans if abs(s["size"] - max_size) < 1.0]
            # Maintain reading order (by y coordinate, then x coordinate)
            title_spans.sort(key=lambda s: (s["origin"][1], s["origin"][0]))
            
            extracted_title = " ".join([s["text"] for s in title_spans]).strip()
            if len(extracted_title) > 10:
                metadata["title"] = clean_extracted_text(extracted_title)
                title_extracted = True
                
            # Authors are usually in spans below the title with smaller font size
            # Find spans with size smaller than title but larger than body text (e.g. 10pt - 14pt)
            # Find y coordinates below title
            title_bottom_y = max([s["bbox"][3] for s in title_spans]) if title_spans else 100
            
            author_spans = [
                s for s in spans 
                if s["origin"][1] > title_bottom_y 
                and s["origin"][1] < title_bottom_y + 150
                and s["size"] < max_size
                and s["size"] > 8.5
            ]
            # Sort by origin
            author_spans.sort(key=lambda s: (s["origin"][1], s["origin"][0]))
            
            # Heuristically compile authors text
            authors_text = " ".join([s["text"] for s in author_spans]).strip()
            # Clean up author names (exclude emails, departments, or institutions if matching keywords)
            lines = [l.strip() for l in authors_text.split("\n") if l.strip()]
            valid_author_lines = []
            for line in lines:
                if any(x in line.lower() for x in ["university", "department", "email", "@", "institute", "laboratory"]):
                    continue
                valid_author_lines.append(line)
            
            if valid_author_lines:
                metadata["authors"] = clean_extracted_text(", ".join(valid_author_lines))
                authors_extracted = True
                
    except Exception as e:
        logger.warning(f"Heuristic font-based metadata extraction failed: {str(e)}")

    # Clean up title if it matches file name or is too short
    if len(metadata["title"]) < 5 or metadata["title"].lower().endswith(".pdf"):
        metadata["title"] = file_path.stem.replace("_", " ").title()

    doc.close()
    
    return metadata, full_text

def extract_pdf_sections(file_path: Path) -> List[Dict[str, Any]]:
    """Helper to extract sections, subsections, and page numbers from PDF.
    This creates structured headings maps for semantic chunking.
    """
    doc = fitz.open(str(file_path))
    sections = []
    
    # Common section patterns
    section_regex = re.compile(
        r'^(?:[IVXLCDM]+\.?\s+|[0-9]+(?:\.[0-9]+)*\.?\s+|Abstract|Keywords|References|Acknowledge?ments)\b.*',
        re.IGNORECASE
    )
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("blocks")
        sorted_blocks = sort_blocks_by_layout(blocks)
        
        for b in sorted_blocks:
            line = b[4].strip()
            # If line matches section heading structure and is short (typically < 100 characters)
            if len(line) < 100 and section_regex.match(line):
                # Split multiple lines inside block
                lines = [l.strip() for l in line.split("\n") if l.strip()]
                for l in lines:
                    if section_regex.match(l):
                        sections.append({
                            "heading": l,
                            "page": page_num + 1,
                            "bbox": (b[0], b[1], b[2], b[3])
                        })
                        
    doc.close()
    return sections
