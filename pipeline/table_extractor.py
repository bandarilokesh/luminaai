import pdfplumber
import json
from pathlib import Path
from typing import List, Dict, Any
from utils.logger import logger

def extract_tables_from_pdf(file_path: Path) -> List[Dict[str, Any]]:
    """
    Extract tables from a PDF using pdfplumber.
    Returns a list of structured table dictionaries.
    """
    tables = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                extracted_tables = page.extract_tables()
                for i, table in enumerate(extracted_tables):
                    if not table:
                        continue
                        
                    # Clean up table by replacing None with empty strings
                    cleaned_table = []
                    for row in table:
                        cleaned_row = [cell.strip().replace("\n", " ") if cell else "" for cell in row]
                        # Only keep rows that aren't entirely empty
                        if any(cleaned_row):
                            cleaned_table.append(cleaned_row)
                            
                    if len(cleaned_table) > 1: # Require at least a header and one data row
                        tables.append({
                            "type": "table",
                            "page": page_num + 1,
                            "table_index": i + 1,
                            "content": cleaned_table,
                            # Serialize to markdown-like format for LLM consumption
                            "markdown": _table_to_markdown(cleaned_table)
                        })
    except Exception as e:
        logger.error(f"Error extracting tables from {file_path}: {e}")
        
    return tables

def _table_to_markdown(table: List[List[str]]) -> str:
    """Converts a 2D list into a Markdown formatted table."""
    if not table:
        return ""
        
    md = []
    # Header
    header = table[0]
    md.append("| " + " | ".join(header) + " |")
    # Separator
    md.append("|" + "|".join(["---"] * len(header)) + "|")
    # Rows
    for row in table[1:]:
        # Pad row to match header length if needed
        row = row + [""] * max(0, len(header) - len(row))
        # Truncate if longer than header
        row = row[:len(header)]
        md.append("| " + " | ".join(row) + " |")
        
    return "\n".join(md)
