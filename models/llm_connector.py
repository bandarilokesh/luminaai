from typing import Optional
from services.gemini_client import gemini_client
from services.ollama_client import ollama_client
from config.settings import settings
from utils.logger import logger

def query_llm(
    prompt: str, 
    model_name: str = None, 
    system_prompt: Optional[str] = None, 
    temperature: float = None, 
    max_tokens: int = None
) -> str:
    """Sends a query to LLM provider (Gemini or Ollama) with system prompt support."""
    model = model_name or settings.MODEL_NAME
    
    if model.startswith("ollama/") or settings.LLM_PROVIDER.lower() == "ollama":
        return ollama_client.generate_chat_response(
            prompt=prompt,
            model_name=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
    else:
        return gemini_client.generate_chat_response(
            prompt=prompt,
            model_name=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

def stream_llm(
    prompt: str, 
    model_name: str = None, 
    system_prompt: Optional[str] = None, 
    temperature: float = None, 
    max_tokens: int = None
):
    """Streams a query to LLM provider (Gemini or Ollama) with system prompt support."""
    model = model_name or settings.MODEL_NAME
    
    if model.startswith("ollama/") or settings.LLM_PROVIDER.lower() == "ollama":
        return ollama_client.generate_chat_stream(
            prompt=prompt,
            model_name=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
    else:
        return gemini_client.generate_chat_stream(
            prompt=prompt,
            model_name=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
