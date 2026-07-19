from typing import Dict, Any, List
from agents.base import BaseAgent
from models.llm_connector import query_llm
from database.db_helper import db
from utils.logger import logger
from rag.retriever import retrieve_context

class ReviewerAgent(BaseAgent):
    """
    Acts as a Peer Reviewer to critique a paper's methodology and claims.
    """
    
    @property
    def name(self) -> str:
        return "Peer Reviewer Agent"
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expects 'paper_ids' in context. Critiques the first paper in the list.
        """
        paper_ids = context.get("paper_ids", [])
        if not paper_ids:
            return {"error": "No paper IDs provided."}
            
        target_paper_id = paper_ids[0]
        model_name = context.get("model_name", None)
        
        # 1. Fetch metadata
        meta = db.get_paper(target_paper_id)
        if not meta:
            return {"error": "Paper not found."}
            
        # 2. Retrieve methodology and limitations sections
        chunks = retrieve_context(
            "methodology, datasets, experimental setup, limitations, weaknesses, future work", 
            [target_paper_id], 
            top_k=15
        )
        
        context_str = ""
        for c in chunks:
            context_str += f"{c.get('text_snippet')}\n\n"
            
        prompt = f"""You are a rigorous, highly-cited academic Peer Reviewer for a top-tier conference.
You are reviewing the paper: "{meta['title']}".

Based on the provided excerpts from the paper, write a detailed methodology critique.
Evaluate:
1. Robustness of the methodology and experimental setup.
2. Validity of the evaluation metrics and datasets.
3. Logical soundness of the claims made versus the evidence provided.
4. What are the key weaknesses the authors missed or downplayed?

EXCERPTS:
{context_str}

PEER REVIEW CRITIQUE (output clean plain text only, no Markdown formatting, no hashtags, no asterisks, no bold/italic, no tables, no horizontal rules):"""

        try:
            review = query_llm(
                prompt=prompt,
                model_name=model_name,
                system_prompt="You write harsh but fair academic peer reviews in clean plain text format. Never use Markdown formatting.",
                temperature=0.2
            )
            return {"review": review, "paper_critiqued": meta["title"]}
        except Exception as e:
            logger.error(f"Error generating critique: {e}")
            return {"error": str(e)}
