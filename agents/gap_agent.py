import json
from typing import Dict, Any, List
from agents.base import BaseAgent
from models.llm_connector import query_llm
from database.db_helper import db
from utils.logger import logger
from rag.retriever import retrieve_context
from knowledge.graph_store import graph_store

class GapAgent(BaseAgent):
    """
    Identifies research gaps and future work across a corpus.
    """
    
    @property
    def name(self) -> str:
        return "Research Gap Agent"
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expects 'paper_ids' in context.
        """
        paper_ids = context.get("paper_ids", [])
        if not paper_ids:
            return {"error": "No paper IDs provided."}
            
        model_name = context.get("model_name", None)
        
        # 1. Fetch Structured Knowledge for future work and limitations
        structured_gaps = ""
        try:
            conn = db._get_connection()
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(paper_ids))
            cursor.execute(
                f"SELECT entity_name, entity_value, paper_id FROM structured_knowledge WHERE entity_type IN ('limitations', 'future_work') AND paper_id IN ({placeholders})",
                paper_ids
            )
            for row in cursor.fetchall():
                structured_gaps += f"Paper ID: {row['paper_id']} | Type: {row['entity_name']} | Detail: {row['entity_value']}\n"
            conn.close()
        except Exception as e:
            logger.error(f"Error fetching DB gaps: {e}")
            
        # 2. Retrieve dense context as backup
        chunks = retrieve_context("limitations, weaknesses, future work, open problems, missing experiments", paper_ids, top_k=10)
        context_str = ""
        for c in chunks:
            context_str += f"{c.get('text_snippet')}\n\n"
            
        prompt = f"""You are a visionary AI Research Director.
Analyze the following extracted limitations, future works, and excerpts from a set of papers to identify high-value, unaddressed research gaps.

What is missing? What are the logical next steps that nobody has done yet?

STRUCTURED KNOWLEDGE:
{structured_gaps}

TEXT EXCERPTS:
{context_str}

Output a plain text report detailing the top 3-5 Research Gaps. For each gap, provide:
- The Problem (What is missing/broken)
- Why it matters
- A proposed direction for solving it based on the texts.

FORMATTING: Output ONLY clean plain text. No Markdown formatting whatsoever: no hashtags (#), no asterisks (*), no bold/italic, no table pipes (|), no horizontal rules (---), no backticks. Use simple numbered lists and line breaks."""

        try:
            gaps = query_llm(
                prompt=prompt,
                model_name=model_name,
                system_prompt="You are a visionary researcher.",
                temperature=0.4
            )
            return {"research_gaps": gaps, "papers_analyzed": len(paper_ids)}
        except Exception as e:
            logger.error(f"Error generating research gaps: {e}")
            return {"error": str(e)}
