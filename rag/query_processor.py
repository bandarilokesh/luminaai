from typing import List, Dict, Any
from models.llm_connector import query_llm
from utils.logger import logger
import json

QUERY_EXPANSION_PROMPT = """You are an AI research assistant. Your task is to take a user's query and expand it into 3 alternative formulations to improve search retrieval in a vector database.
Use synonyms, broaden the scope slightly, or rephrase to catch different terminology often used in academic papers.

Original query: "{query}"

Output ONLY a JSON array of exactly 3 strings (the alternative queries).
"""

HYDE_PROMPT = """You are an expert researcher. Please write a short, hypothetical academic paragraph that directly answers the following question.
Do not worry if the facts are perfectly accurate; the goal is to generate text that looks like a research paper's answer to this question, which will be used for dense vector retrieval.

Question: "{query}"

Hypothetical Answer:"""

def expand_query(query: str, model_name: str = None) -> List[str]:
    """Generates alternative formulations of the query."""
    try:
        response = query_llm(
            prompt=QUERY_EXPANSION_PROMPT.format(query=query),
            model_name=model_name,
            system_prompt="You are a helpful API that outputs only JSON arrays of strings.",
            temperature=0.7
        )
        
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
            
        expanded = json.loads(response.strip())
        if isinstance(expanded, list):
            return [str(q) for q in expanded]
    except Exception as e:
        logger.error(f"Error in query expansion: {e}")
        
    return []

def generate_hyde_document(query: str, model_name: str = None) -> str:
    """Generates a hypothetical document (HyDE) for a query."""
    try:
        response = query_llm(
            prompt=HYDE_PROMPT.format(query=query),
            model_name=model_name,
            system_prompt="You write in dense, academic language.",
            temperature=0.7,
            max_tokens=150
        )
        return response.strip()
    except Exception as e:
        logger.error(f"Error in HyDE generation: {e}")
        return ""
