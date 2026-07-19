import json
from typing import List, Dict, Any
from models.llm_connector import query_llm
from knowledge.graph_store import graph_store
from utils.logger import logger

class RelationshipDetector:
    """
    Detects cross-document relationships (contradictions, agreements) using the knowledge graph and LLMs.
    """
    
    CONTRADICTION_PROMPT = """You are an expert AI Research Analyst.
Given the following extracted entities and claims from multiple papers, identify if there are any direct contradictions or disagreements between the papers.

Look for:
1. Conflicting results on the same dataset.
2. Contradictory claims about a method's effectiveness.
3. Disagreements in theoretical findings.

Data:
{data}

Output ONLY a JSON array of objects representing contradictions:
[
  {{
    "paper1_id": "string",
    "paper2_id": "string",
    "topic": "string",
    "contradiction_description": "string",
    "severity": "high/medium/low"
  }}
]
"""

    def detect_contradictions(self, paper_ids: List[str], model_name: str = None) -> List[Dict[str, Any]]:
        """Finds contradictions among the provided papers."""
        if len(paper_ids) < 2:
            return []
            
        try:
            # Load graph for these papers
            graph = graph_store.load_graph(paper_ids)
            
            # Serialize graph data for LLM
            data_text = ""
            for node, attr in graph.nodes(data=True):
                if attr.get("type") == "Paper":
                    continue
                data_text += f"Entity: {node} | Type: {attr.get('type')} | Paper ID: {attr.get('paper_id')} | Value: {attr.get('value', '')}\n"
                
            if not data_text.strip():
                return []
                
            # Query LLM
            response = query_llm(
                prompt=self.CONTRADICTION_PROMPT.format(data=data_text[:30000]), # limit context
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
                
            contradictions = json.loads(response.strip())
            return contradictions if isinstance(contradictions, list) else []
            
        except Exception as e:
            logger.error(f"Error detecting contradictions: {e}")
            return []

relationship_detector = RelationshipDetector()
