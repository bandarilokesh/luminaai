import json
from typing import Dict, Any, List
from agents.base import BaseAgent
from models.llm_connector import query_llm
from database.db_helper import db
from utils.logger import logger

class ResearchAgent(BaseAgent):
    """
    Performs cross-document analysis and generates comparison tables.
    """
    
    @property
    def name(self) -> str:
        return "Research Agent"
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expects 'paper_ids' in context.
        Pulls structured knowledge from DB and generates a comparison table.
        """
        paper_ids = context.get("paper_ids", [])
        if not paper_ids:
            return {"error": "No paper IDs provided."}
            
        # 1. Fetch structured knowledge from database
        papers_data = {}
        for p_id in paper_ids:
            paper_meta = db.get_paper(p_id)
            if not paper_meta:
                continue
                
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT entity_type, entity_name, entity_value, metadata_json FROM structured_knowledge WHERE paper_id = ?", (p_id,))
            
            entities = {}
            for row in cursor.fetchall():
                e_type = row["entity_type"]
                if e_type not in entities:
                    entities[e_type] = []
                entities[e_type].append({
                    "name": row["entity_name"],
                    "value": row["entity_value"],
                    "metadata": json.loads(row["metadata_json"])
                })
            
            papers_data[paper_meta["title"]] = entities
            conn.close()
            
        # 2. Construct LLM prompt for comparison
        prompt = "You are a Research Assistant. Create a detailed structured comparison across the following research papers based on their extracted structured knowledge.\n\n"
        prompt += "Focus on comparing their Methods, Datasets, Metrics, and Key Limitations.\n\n"
        
        for title, data in papers_data.items():
            prompt += f"### Paper: {title}\n"
            prompt += f"{json.dumps(data, indent=2)}\n\n"
            
        prompt += "Output ONLY the final structured comparison and a short 1-paragraph synthesis. Use clean plain text only. Do NOT use any Markdown formatting whatsoever: no hashtags (#), no asterisks (*), no bold/italic markers, no table pipes (|), no horizontal rules (---), no backticks. Use simple labels and line breaks to organize the comparison."
        
        try:
            llm_model = context.get("model_name", None)
            result = query_llm(
                prompt=prompt,
                model_name=llm_model,
                system_prompt="You are an expert at synthesizing academic data into structured comparisons. Output clean plain text only, never use Markdown formatting.",
                temperature=0.2
            )
            return {"comparison_table": result, "papers_compared": list(papers_data.keys())}
        except Exception as e:
            logger.error(f"Error in ResearchAgent: {e}")
            return {"error": str(e)}
