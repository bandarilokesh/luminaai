import requests
import json
from typing import Optional
from config.settings import settings
from utils.logger import logger

class OllamaClient:
    """Client for generating completions using a local Ollama instance."""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_API_URL.rstrip('/')
        
    def is_configured(self) -> bool:
        """Checks if Ollama is running."""
        try:
            r = requests.get(self.base_url)
            return r.status_code == 200
        except:
            return False

    def generate_chat_response(
        self,
        prompt: str,
        model_name: str = None,
        system_prompt: Optional[str] = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        
        model = model_name or settings.MODEL_NAME
        # Remove 'ollama/' prefix if present
        if model.startswith("ollama/"):
            model = model[7:]
            
        temp = temperature if temperature is not None else settings.TEMPERATURE
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temp
            }
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
            
        try:
            r = requests.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    def generate_chat_stream(
        self,
        prompt: str,
        model_name: str = None,
        system_prompt: Optional[str] = None,
        temperature: float = None,
        max_tokens: int = None
    ):
        model = model_name or settings.MODEL_NAME
        if model.startswith("ollama/"):
            model = model[7:]
            
        temp = temperature if temperature is not None else settings.TEMPERATURE
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temp
            }
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
            
        try:
            with requests.post(f"{self.base_url}/api/chat", json=payload, stream=True) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        chunk = json.loads(line.decode('utf-8'))
                        if "message" in chunk and "content" in chunk["message"]:
                            yield chunk["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama stream generation failed: {e}")
            raise

ollama_client = OllamaClient()
