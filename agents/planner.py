from typing import Dict, Any, List
import json
from models.llm_connector import query_llm
from utils.logger import logger

class PlannerAgent:
    """
    Classifies user intent and routes the query to the correct specialized agent.
    """
    
    INTENT_PROMPT = """You are the orchestration planner for an AI Research Assistant.
Given a user query and the available tools, determine the user's intent.

INTENTS:
1. "qa": The user is asking a factual question to be answered from the papers.
2. "literature_review": The user wants a summary or synthesis of multiple papers.
3. "methodology_critique": The user wants an analysis or critique of how the research was conducted.
4. "research_gaps": The user wants to find limitations, future work, or open problems.
5. "comparison": The user wants to compare papers (methods, datasets, metrics).

USER QUERY:
"{query}"

Output ONLY a JSON object:
{{"intent": "<one of the intents above>"}}
"""

    def determine_intent(self, query: str, model_name: str = None) -> str:
        """Determines the intent of a query using the LLM."""
        try:
            response = query_llm(
                prompt=self.INTENT_PROMPT.format(query=query),
                model_name=model_name,
                system_prompt="You are a JSON-only API.",
                temperature=0.0
            )
            
            # Clean JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
                
            data = json.loads(response.strip())
            return data.get("intent", "qa")
        except Exception as e:
            logger.error(f"Failed to determine intent: {e}")
            return "qa" # default to QA

planner = PlannerAgent()
