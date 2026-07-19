from typing import Dict, Any, List
from agents.base import BaseAgent
from models.llm_connector import query_llm
from database.db_helper import db
from utils.logger import logger
from rag.retriever import retrieve_context

class SummaryAgent(BaseAgent):
    """
    Generates literature reviews or cross-document summaries.
    """
    
    @property
    def name(self) -> str:
        return "Literature Review Agent"
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expects 'paper_ids' and optionally 'topic' in context.
        """
        paper_ids = context.get("paper_ids", [])
        topic = context.get("topic", "General Research Synthesis")
        model_name = context.get("model_name", None)
        
        if not paper_ids:
            return {"error": "No paper IDs provided."}
            
        # 1. Fetch metadata
        papers_meta = []
        for p_id in paper_ids:
            meta = db.get_paper(p_id)
            if meta:
                papers_meta.append(meta)
                
        if not papers_meta:
            return {"error": "No valid papers found in DB."}
            
        # 2. Retrieve relevant chunks across papers based on the topic
        # If no specific topic is given, we could just use the abstracts, but let's do a broad retrieve
        chunks = retrieve_context(topic, paper_ids, top_k=20)
        context_str = ""
        for i, c in enumerate(chunks):
            context_str += f"--- Paper: {c.get('paper_name')} ---\n{c.get('text_snippet')}\n\n"
            
        # 3. Add Abstracts as baseline context
        abstracts = ""
        for p in papers_meta:
            abstracts += f"--- Abstract: {p['title']} ---\n{p['abstract']}\n\n"
            
        prompt = f"""You are an expert AI Research Scientist.
Write a comprehensive Literature Review synthesizing the following research papers.
The central topic/theme is: {topic}

Use the provided abstracts and detailed excerpts from the papers to construct the review.
Organize the review into:
1. Introduction & Background
2. Core Methodologies & Approaches
3. Key Findings & Results
4. Synthesis & Conclusion

ABSTRACTS:
{abstracts}

EXCERPTS:
{context_str}

LITERATURE REVIEW (output clean plain text only, no Markdown formatting, no hashtags, no asterisks, no bold/italic, no tables, no horizontal rules):"""

        try:
            review = query_llm(
                prompt=prompt,
                model_name=model_name,
                system_prompt="You write professional, academic literature reviews in clean plain text format. Never use Markdown formatting.",
                temperature=0.3
            )
            return {"literature_review": review, "papers_synthesized": [p["title"] for p in papers_meta]}
        except Exception as e:
            logger.error(f"Error generating literature review: {e}")
            return {"error": str(e)}
