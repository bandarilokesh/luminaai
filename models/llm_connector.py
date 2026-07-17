from typing import Optional
from services.gemini_client import gemini_client
from utils.logger import logger

def query_llm(
    prompt: str, 
    model_name: str = None, 
    system_prompt: Optional[str] = None, 
    temperature: float = None, 
    max_tokens: int = None
) -> str:
    """Sends a query to LLM provider with system prompt support."""
    return gemini_client.generate_chat_response(
        prompt=prompt,
        model_name=model_name,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens
    )
