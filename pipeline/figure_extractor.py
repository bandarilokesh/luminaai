import pdfplumber
from typing import List, Dict, Any
from utils.logger import logger
from pathlib import Path

class FigureExtractor:
    """
    Extracts figures/images and their captions from a PDF.
    """
    
    def extract_figures(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extracts figures and their bounding boxes/images.
        """
        figures = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    for img in page.images:
                        # Extract basic image info
                        fig_info = {
                            "page": i + 1,
                            "bbox": (img["x0"], img["top"], img["x1"], img["bottom"]),
                            "width": img["width"],
                            "height": img["height"],
                            "type": "Figure"
                        }
                        figures.append(fig_info)
                        
            logger.info(f"Extracted {len(figures)} potential figures from {pdf_path}")
            return figures
        except Exception as e:
            logger.error(f"Failed to extract figures from {pdf_path}: {e}")
            return []

figure_extractor = FigureExtractor()
