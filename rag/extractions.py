import json
import re
from typing import List, Dict, Any
from config.settings import settings
from utils.logger import logger
from rag.retriever import get_all_chunks_for_papers
from models.prompt_templates import QUIZ_GENERATOR_PROMPT, FLASHCARD_GENERATOR_PROMPT, GAP_DETECTOR_PROMPT
from models.llm_connector import query_llm

def extract_json_from_text(text: str) -> Any:
    """Robust helper to extract and parse JSON array from LLM text responses, handling markdown code fences."""
    if not text:
        return []
        
    cleaned = text.strip()
    
    # 1. Look for markdown code fences (e.g. ```json [...] ``` or ``` [...] ```)
    fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned, re.IGNORECASE)
    if fence_match:
        json_content = fence_match.group(1).strip()
    else:
        json_content = cleaned
        
    # 2. Find first [ and last ] to extract array block
    array_match = re.search(r'(\[\s*[\s\S]*\s*\])', json_content)
    if array_match:
        json_content = array_match.group(1).strip()
        
    try:
        return json.loads(json_content)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {str(e)} | Raw text content: {text}")
        
        # Fallback regex parser for simple items if JSON fails
        # Let's try parsing manually or return empty list
        return []

def get_core_context(paper_ids: List[str], limit: int = 6) -> str:
    """Assembles a concise global context of the selected papers (mainly Abstracts and Introductions)."""
    context_blocks = []
    for p_id in paper_ids:
        chunks = get_all_chunks_for_papers([p_id])
        if not chunks:
            continue
        # Take abstract and first few chunks
        abstract_chunks = [c for c in chunks if "abstract" in c.get("section", "").lower()]
        intro_chunks = [c for c in chunks if "introduction" in c.get("section", "").lower()]
        
        selected = abstract_chunks + intro_chunks
        if not selected:
            selected = chunks[:3]
            
        for c in selected[:limit]:
            context_blocks.append(f"--- Paper: {c['paper_name']} (Page {c['page']}) ---\n{c['text']}")
            
    return "\n\n".join(context_blocks)

def generate_quiz(paper_ids: List[str], quiz_type: str, difficulty: str, num_questions: int) -> List[Dict[str, Any]]:
    """Generates an academic quiz over selected papers."""
    logger.info(f"Generating quiz (type: {quiz_type}, diff: {difficulty}, count: {num_questions}) for papers: {paper_ids}")
    
    context = get_core_context(paper_ids, limit=4)
    if not context:
        return []
        
    prompt = QUIZ_GENERATOR_PROMPT.format(
        difficulty=difficulty.title(),
        quiz_type=quiz_type,
        num_questions=num_questions,
        text=context
    )
    
    system_instruction = "You are an academic test designer. Return ONLY a valid JSON array of quiz objects as requested. Do NOT print markdown fences or chat intro/outro."
    response = query_llm(
        prompt=prompt,
        system_prompt=system_instruction,
        temperature=0.3
    )
    
    quiz_items = extract_json_from_text(response)
    
    # Validation fallback
    if not quiz_items:
        # Create a friendly mock fallback in case of local LLM formatting error
        quiz_items = [
            {
                "question": f"A key concept discussed in these papers was related to: {paper_ids[0][:8]}",
                "options": ["Model architecture", "Dataset limitations", "Hyperparameters tuning", "Evaluation metrics"],
                "answer": "Model architecture",
                "explanation": "Please review the paper text directly. The local model failed to serialize the questions in JSON."
            }
        ]
        
    return quiz_items

def generate_flashcards(paper_ids: List[str], num_cards: int) -> List[Dict[str, Any]]:
    """Generates study flashcards from paper key concepts."""
    logger.info(f"Generating {num_cards} flashcards for papers: {paper_ids}")
    
    context = get_core_context(paper_ids, limit=4)
    if not context:
        return []
        
    prompt = FLASHCARD_GENERATOR_PROMPT.format(
        num_cards=num_cards,
        text=context
    )
    
    system_instruction = "You are an academic study assistant. Return ONLY a valid JSON array of flashcard objects. Do NOT print markdown fences or chat intro/outro."
    response = query_llm(
        prompt=prompt,
        system_prompt=system_instruction,
        temperature=0.3
    )
    
    cards = extract_json_from_text(response)
    
    if not cards:
        cards = [
            {
                "front": "Paper Contribution",
                "back": "The primary contribution details presented in the selected research paper.",
                "explanation": "Note: Local LLM failed to compile JSON flashcards. Check terminal logs."
            }
        ]
        
    return cards

def detect_research_gaps(paper_ids: List[str]) -> List[Dict[str, Any]]:
    """Scans papers for limitations, missing experiments, conflicts and future opportunities."""
    logger.info(f"Running research gap detector on papers: {paper_ids}")
    
    # Gather context from conclusion/future work sections
    context_blocks = []
    for p_id in paper_ids:
        chunks = get_all_chunks_for_papers([p_id])
        if not chunks:
            continue
        # Take conclusion, future work, limitations sections
        target_chunks = [
            c for c in chunks 
            if any(k in c.get("section", "").lower() for k in ["conclusion", "limitation", "future", "discussion"])
        ]
        # Fallback to last few pages
        if not target_chunks:
            target_chunks = chunks[-3:]
            
        for c in target_chunks[:5]:
            context_blocks.append(f"--- Paper: {c['paper_name']} (Page {c['page']}) ---\n{c['text']}")
            
    context = "\n\n".join(context_blocks)
    if not context:
        return []
        
    prompt = GAP_DETECTOR_PROMPT.format(text=context)
    
    system_instruction = "You are a research auditor. Return ONLY a valid JSON array of identified gaps and limitations. Do NOT print markdown fences or chat intro/outro."
    response = query_llm(
        prompt=prompt,
        system_prompt=system_instruction,
        temperature=0.2
    )
    
    gaps = extract_json_from_text(response)
    
    if not gaps:
        gaps = [
            {
                "section": "General Analysis",
                "gap_description": "Review the conclusion and limitations section of the papers directly. The local model failed to format the gap list in JSON.",
                "confidence": "medium"
            }
        ]
        
    return gaps
