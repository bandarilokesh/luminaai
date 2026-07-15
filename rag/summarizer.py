from typing import List, Dict, Any
from config.settings import settings
from utils.logger import logger
from rag.retriever import get_all_chunks_for_papers
from models.prompt_templates import SUMMARY_PROMPTS
from models.llm_connector import query_llm

def get_summary_context(paper_id: str, summary_type: str) -> str:
    """Retrieve relevant chunks for the selected summarization perspective from paper metadata."""
    chunks = get_all_chunks_for_papers([paper_id])
    if not chunks:
        return ""
        
    # Group chunks by section matching
    selected_chunks = []
    
    summary_type = summary_type.lower()
    
    if summary_type == "abstract":
        selected_chunks = [c for c in chunks if "abstract" in c.get("section", "").lower()]
        # Fallback to first 2 chunks
        if not selected_chunks:
            selected_chunks = chunks[:2]
            
    elif summary_type == "methodology":
        keywords = ["method", "experiment", "model", "architecture", "setup", "algorithm", "dataset"]
        selected_chunks = [
            c for c in chunks 
            if any(k in c.get("section", "").lower() for k in ["method", "setup", "experiment"])
        ]
        # Fallback to scoring search
        if not selected_chunks:
            selected_chunks = [
                c for c in chunks 
                if any(k in c["text"].lower() for k in keywords)
            ]
            selected_chunks = selected_chunks[:6] # Limit context size
            
    elif summary_type == "results":
        keywords = ["result", "discussion", "table", "figure", "accuracy", "performance", "metric"]
        selected_chunks = [
            c for c in chunks 
            if any(k in c.get("section", "").lower() for k in ["result", "discussion", "evaluation"])
        ]
        if not selected_chunks:
            selected_chunks = [
                c for c in chunks 
                if any(k in c["text"].lower() for k in keywords)
            ]
            selected_chunks = selected_chunks[:6]
            
    elif summary_type == "conclusion":
        selected_chunks = [c for c in chunks if "conclusion" in c.get("section", "").lower()]
        # Fallback to last 2 chunks
        if not selected_chunks:
            selected_chunks = chunks[-2:]
            
    else:
        # Global summaries (beginner, technical, bullet, one-page)
        # Assemble core context: Abstract chunks + Conclusion chunks + first few pages
        abstract_chunks = [c for c in chunks if "abstract" in c.get("section", "").lower()][:2]
        conclusion_chunks = [c for c in chunks if "conclusion" in c.get("section", "").lower()][:2]
        intro_chunks = chunks[:3]
        
        # Merge unique chunks
        seen_ids = set()
        merged = []
        for c in abstract_chunks + intro_chunks + conclusion_chunks:
            if c["chunk_id"] not in seen_ids:
                seen_ids.add(c["chunk_id"])
                merged.append(c)
        selected_chunks = merged[:7] # Safe upper bound for local LLM context
        
    # Compile text context
    context_text = "\n\n".join([f"--- Chunk from Page {c['page']} (Section: {c.get('section', 'N/A')}) ---\n{c['text']}" for c in selected_chunks])
    return context_text

def generate_paper_summary(paper_id: str, summary_type: str, model_name: str) -> str:
    """Retrieves relevant paper context, constructs prompt, and queries LLM to generate summary."""
    logger.info(f"Generating summary brief (type: {summary_type}) for paper {paper_id} using {model_name}...")
    
    # 1. Fetch relevant context text
    context_text = get_summary_context(paper_id, summary_type)
    if not context_text:
        return "Could not retrieve text content from paper to generate summary."
        
    # 2. Get prompt template
    prompt_template = SUMMARY_PROMPTS.get(summary_type.lower())
    if not prompt_template:
        raise ValueError(f"Unknown summary type requested: {summary_type}")
        
    # 3. Format prompt
    formatted_prompt = prompt_template.format(text=context_text)
    
    # 4. Query local LLM
    system_instruction = "You are a professional research scientist. Generate a factual, citation-backed, clear summary brief based ONLY on the provided text."
    summary_result = query_llm(
        prompt=formatted_prompt,
        model_name=model_name,
        system_prompt=system_instruction,
        temperature=0.2 # Slightly higher temperature for summary flows, but still low
    )
    
    return summary_result
