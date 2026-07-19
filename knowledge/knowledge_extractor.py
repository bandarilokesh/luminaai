import json
from typing import Dict, Any, List
from models.llm_connector import query_llm
from utils.logger import logger
from database.db_helper import db

EXTRACTION_PROMPT = """You are an expert academic data extractor. Your task is to extract structured knowledge from the provided research paper text.
Extract the information into the following categories:
- methods: Key algorithms, models, or theoretical frameworks proposed or used.
- datasets: Data collections used for training or evaluation.
- metrics: Evaluation metrics and key results.
- baselines: Prior methods compared against.
- limitations: Weaknesses or scope limits acknowledged by authors.
- future_work: Next steps proposed by authors.
- novel_contributions: The core novelties introduced in this paper.

Output ONLY a valid JSON object matching the following structure:
{
    "methods": [{"name": "string", "category": "string", "description": "string"}],
    "datasets": [{"name": "string", "domain": "string", "size": "string"}],
    "metrics": [{"name": "string", "value": "string", "dataset": "string", "is_sota": boolean}],
    "baselines": [{"name": "string", "metric": "string", "value": "string"}],
    "limitations": ["string"],
    "future_work": ["string"],
    "novel_contributions": ["string"]
}

PAPER TEXT:
{text}
"""

def extract_structured_knowledge(paper_id: str, paper_text: str, model_name: str = None) -> Dict[str, Any]:
    """
    Extracts structured knowledge from paper text and saves it to the database.
    """
    # For a full paper, we might need to chunk it or just pass the summary/method/results sections.
    # To avoid context limits, we truncate to first 20000 characters for now if it's too long.
    text_to_process = paper_text[:20000]
    
    prompt = EXTRACTION_PROMPT.format(text=text_to_process)
    
    try:
        response = query_llm(
            prompt=prompt,
            model_name=model_name,
            system_prompt="You are a strict JSON-only API.",
            temperature=0.1
        )
        
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        # Find the JSON object boundaries robustly
        response = response.strip()
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            raise ValueError(f"No valid JSON object found in LLM response: {response[:200]}")
        response = response[start_idx:end_idx + 1]
            
        data = json.loads(response)
        
        # Save to database
        _save_knowledge_to_db(paper_id, data)
        
        return data
    except Exception as e:
        logger.error(f"Failed to extract structured knowledge for {paper_id}: {e}")
        return {}

def _save_knowledge_to_db(paper_id: str, data: Dict[str, Any]):
    """Persists extracted structured knowledge to the database."""
    conn = db._get_connection()
    try:
        cursor = conn.cursor()
        
        # Helper to insert entities
        def insert_entity(entity_type: str, item: Any):
            name = ""
            val = ""
            meta = {}
            if isinstance(item, dict):
                name = item.get("name", "")
                val = item.get("value", "") or item.get("description", "")
                meta = {k: v for k, v in item.items() if k not in ["name", "value", "description"]}
            elif isinstance(item, str):
                name = item
                
            cursor.execute("""
                INSERT INTO structured_knowledge (paper_id, entity_type, entity_name, entity_value, metadata_json)
                VALUES (?, ?, ?, ?, ?)
            """, (paper_id, entity_type, str(name), str(val), json.dumps(meta)))

        # Process each category
        for category, items in data.items():
            if isinstance(items, list):
                for item in items:
                    insert_entity(category, item)
                    
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving structured knowledge to DB: {e}")
    finally:
        conn.close()
