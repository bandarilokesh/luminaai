import json
from typing import List, Dict, Any
from models.llm_connector import query_llm
from utils.logger import logger

class RAGEvaluator:
    """
    Evaluates RAG pipeline performance (Faithfulness, Answer Relevance, Context Precision)
    using LLM-as-a-judge (similar to RAGAS).
    """

    FAITHFULNESS_PROMPT = """You are an expert evaluator. 
Given a question, the retrieved context, and the generated answer, determine the Faithfulness score of the answer.
Faithfulness measures how much of the generated answer can be inferred directly from the context.
Return a score between 0.0 and 1.0 (where 1.0 means all claims in the answer are supported by the context).

Question: {question}
Context: {context}
Answer: {answer}

Output ONLY a valid JSON object with the score and reasoning:
{{"faithfulness_score": 0.8, "reasoning": "string"}}
"""

    def evaluate_faithfulness(self, question: str, context: str, answer: str, model_name: str = None) -> Dict[str, Any]:
        """Evaluates if the answer is faithful to the retrieved context."""
        try:
            res = query_llm(
                prompt=self.FAITHFULNESS_PROMPT.format(question=question, context=context, answer=answer),
                model_name=model_name,
                system_prompt="You are a JSON-only evaluation API.",
                temperature=0.0
            )
            
            res = res.strip()
            if res.startswith("```json"):
                res = res[7:]
            if res.startswith("```"):
                res = res[3:]
            if res.endswith("```"):
                res = res[:-3]
                
            return json.loads(res.strip())
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {"faithfulness_score": 0.0, "reasoning": "Error evaluating"}

rag_evaluator = RAGEvaluator()
