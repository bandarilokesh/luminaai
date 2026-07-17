import os
import time
from google import genai
from google.genai import types
from google.genai.errors import APIError
from typing import Optional, List, Dict, Any
from config.settings import settings
from utils.logger import logger

class GeminiClient:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set in environment or settings.")
            self.client = None
        else:
            # Initialize modern genai Client with custom timeout
            self.client = genai.Client(
                api_key=self.api_key,
                http_options={'timeout': 60000}  # 60s timeout
            )
            
    def is_configured(self) -> bool:
        return self.client is not None

    def generate_chat_response(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Sends a query to Gemini API with system prompt support.
        """
        if not self.is_configured():
            raise ConnectionError(
                "Gemini API Key is not configured. "
                "Please set GEMINI_API_KEY environment variable."
            )
            
        model_id = model_name or settings.MODEL_NAME
        temp = temperature if temperature is not None else settings.TEMPERATURE
        max_tok = max_tokens if max_tokens is not None else settings.MAX_TOKENS
        
        logger.info(f"Querying Gemini LLM '{model_id}' (Temp: {temp}, Max Tokens: {max_tok})...")
        
        start_time = time.time()
        try:
            config = types.GenerateContentConfig(
                temperature=temp,
                max_output_tokens=max_tok,
                system_instruction=system_prompt,
            )
            
            response = self.client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=config,
            )
            
            duration = time.time() - start_time
            logger.info(f"Gemini API query completed successfully in {duration:.2f}s")
            
            return response.text.strip()
            
        except APIError as e:
            duration = time.time() - start_time
            logger.error(f"Gemini API error (Status: {e.code}, Duration: {duration:.2f}s): {e.message}")
            if e.code == 404:
                raise Exception(f"Model '{model_id}' not found. Please verify the model name.") from e
            elif e.code == 429:
                raise Exception("Rate limit exceeded or quota exhausted for Gemini API.") from e
            elif e.code == 401 or e.code == 403:
                raise Exception("Authentication failed. Please verify your GEMINI_API_KEY.") from e
            else:
                raise Exception(f"Gemini API backend error: {e.message}") from e
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Unexpected error when communicating with Gemini (Duration: {duration:.2f}s): {str(e)}")
            raise Exception(f"Failed to communicate with Gemini backend: {str(e)}") from e

# Instantiate singleton client
gemini_client = GeminiClient()
