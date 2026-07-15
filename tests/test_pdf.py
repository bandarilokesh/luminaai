import pytest
from rag.pdf_processor import clean_extracted_text, sort_blocks_by_layout

def test_clean_extracted_text():
    # Test hyphen line break removal
    text_hyphen = "This is a develop-\nment process."
    assert clean_extracted_text(text_hyphen) == "This is a development process."
    
    # Test whitespace normalization
    text_whitespace = "Too   many   spaces \t here."
    assert clean_extracted_text(text_whitespace) == "Too many spaces here."
    
    # Test blank string
    assert clean_extracted_text("") == ""
    assert clean_extracted_text(None) == ""

def test_sort_blocks_by_layout():
    # Mock text blocks (x0, y0, x1, y1, "text", block_no, block_type)
    # block_type 0 = text, 1 = image
    
    # Two-column layout representation
    # Title (spans full page width)
    title = (50, 50, 550, 80, "Research Title", 0, 0)
    # Col 1 block 1 (left side, higher up)
    col1_b1 = (50, 100, 280, 200, "Left column paragraph 1", 1, 0)
    # Col 1 block 2 (left side, lower down)
    col1_b2 = (50, 220, 280, 300, "Left column paragraph 2", 2, 0)
    # Col 2 block 1 (right side, higher up)
    col2_b1 = (320, 100, 550, 200, "Right column paragraph 1", 3, 0)
    # Col 2 block 2 (right side, lower down)
    col2_b2 = (320, 220, 550, 300, "Right column paragraph 2", 4, 0)
    # Image block (should be filtered out)
    img_block = (50, 400, 550, 600, "Image data", 5, 1)
    
    blocks = [col2_b2, col1_b2, title, col2_b1, col1_b1, img_block]
    
    sorted_blocks = sort_blocks_by_layout(blocks)
    
    # Expected order:
    # 1. Title (spans > 65% width)
    # 2. Left column paragraph 1 (y=100)
    # 3. Left column paragraph 2 (y=220)
    # 4. Right column paragraph 1 (y=100)
    # 5. Right column paragraph 2 (y=220)
    # Note: image block is excluded.
    
    assert len(sorted_blocks) == 5
    assert sorted_blocks[0][4] == "Research Title"
    assert sorted_blocks[1][4] == "Left column paragraph 1"
    assert sorted_blocks[2][4] == "Left column paragraph 2"
    assert sorted_blocks[3][4] == "Right column paragraph 1"
    assert sorted_blocks[4][4] == "Right column paragraph 2"
