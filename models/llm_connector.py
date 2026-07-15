import requests
from typing import List, Dict, Any, Optional
from config.settings import settings
from utils.logger import logger

def check_ollama_status() -> bool:
    """Checks if the local Ollama instance is running and reachable."""
    try:
        url = f"{settings.OLLAMA_API_BASE}/"
        r = requests.get(url, timeout=3)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        logger.warning(f"Ollama server not reachable at base url: {settings.OLLAMA_API_BASE}")
        return False

def get_installed_ollama_models() -> List[str]:
    """Fetches list of installed models from local Ollama instance."""
    try:
        url = f"{settings.OLLAMA_API_BASE}/api/tags"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            data = r.json()
            models = [m["name"] for m in data.get("models", [])]
            # Strip tag version suffix if needed, but keeping exact tag is safer for loading
            return models
    except Exception as e:
        logger.error(f"Failed to fetch Ollama models: {str(e)}")
    return []

def query_llm(
    prompt: str, 
    model_name: str = None, 
    system_prompt: Optional[str] = None, 
    temperature: float = None, 
    max_tokens: int = None
) -> str:
    """Sends a query to local Ollama chat endpoint with system prompt support."""
    model_name = model_name or settings.DEFAULT_LLM_MODEL
    temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
    max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS
    
    if not check_ollama_status():
        raise ConnectionError(
            f"Ollama server is not running at {settings.OLLAMA_API_BASE}. "
            "Please start Ollama to enable local AI generations."
        )
        
    url = f"{settings.OLLAMA_API_BASE}/api/chat"
    
    # Structure chat messages
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model_name,
        "messages": messages,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        },
        "stream": False
    }
    
    logger.info(f"Querying local LLM '{model_name}' (Temp: {temperature}, Max Tokens: {max_tokens})...")
    
    try:
        r = requests.post(url, json=payload, timeout=120)
        
        if r.status_code == 200:
            result_json = r.json()
            message_content = result_json.get("message", {}).get("content", "").strip()
            return message_content
            
        elif r.status_code == 404:
            # Model not found on Ollama server
            logger.error(f"Model '{model_name}' not found on Ollama server. Response: {r.text}")
            raise ValueError(
                f"Model '{model_name}' is not downloaded in Ollama. "
                f"Please open terminal and run: `ollama pull {model_name}` to install it."
            )
        else:
            logger.error(f"Ollama returned error: {r.status_code} - {r.text}")
            raise Exception(f"Ollama API returned status code {r.status_code}: {r.text}")
            
    except requests.exceptions.Timeout:
        logger.error(f"Ollama request timed out for model: {model_name}")
        raise TimeoutError("Local LLM request timed out. The model may be too heavy for your current hardware specs.")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network request to Ollama failed: {str(e)}")
        raise ConnectionError(f"Failed to communicate with Ollama backend: {str(e)}")
