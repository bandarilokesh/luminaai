"""LLM: Groq or Gemini, both called through their OpenAI-compatible endpoints.

The clients come from `langfuse.openai`, a drop-in wrapper that records every call as a
Langfuse generation (prompt, output, model, token usage, latency).
"""
import json
import re
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import openai
from langfuse.openai import AsyncOpenAI, OpenAI

from app.config import settings
from app.observability import langfuse  # noqa: F401  (ensures Langfuse is configured first)


class LLMError(RuntimeError):
    pass


def _provider() -> tuple[str, str, str]:
    """(base_url, api_key, model) for the configured provider."""
    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini":
        return settings.GEMINI_BASE_URL, settings.GEMINI_API_KEY, settings.GEMINI_MODEL
    if provider == "groq":
        return settings.GROQ_BASE_URL, settings.GROQ_API_KEY, settings.GROQ_MODEL
    raise LLMError(f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'. Use 'groq' or 'gemini'.")


def is_configured() -> bool:
    try:
        return bool(_provider()[1])
    except LLMError:
        return False


def _require_key(api_key: str) -> None:
    if not api_key:
        name = "GEMINI_API_KEY" if settings.LLM_PROVIDER.lower() == "gemini" else "GROQ_API_KEY"
        raise LLMError(f"{name} is not set in .env")


@lru_cache
def _sync_client() -> tuple[OpenAI, str]:
    base_url, api_key, model = _provider()
    _require_key(api_key)
    return OpenAI(base_url=base_url, api_key=api_key, max_retries=3, timeout=90), model


@lru_cache
def _async_client() -> tuple[AsyncOpenAI, str]:
    base_url, api_key, model = _provider()
    _require_key(api_key)
    return AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=3, timeout=90), model


def _messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]


def _friendly(e: openai.APIError) -> LLMError:
    status = getattr(e, "status_code", None)
    if status == 429:
        return LLMError(f"{settings.LLM_PROVIDER} rate limit / free-tier quota reached. Wait a minute and retry.")
    if status in (401, 403):
        return LLMError(f"{settings.LLM_PROVIDER} rejected the API key. Check your .env.")
    if status == 404:
        return LLMError(f"Model '{settings.llm_model}' was not found on {settings.LLM_PROVIDER}.")
    return LLMError(f"{settings.LLM_PROVIDER} API error: {e}")


def generate(
    system_prompt: str,
    user_prompt: str,
    *,
    name: str,
    json_mode: bool = False,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    client, model = _sync_client()
    kwargs: dict[str, Any] = dict(
        model=model,
        messages=_messages(system_prompt, user_prompt),
        temperature=settings.TEMPERATURE if temperature is None else temperature,
        max_tokens=max_tokens or settings.MAX_TOKENS,
        name=name,  # Langfuse generation name
    )
    try:
        if json_mode:
            try:
                response = client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
            except openai.BadRequestError:
                response = client.chat.completions.create(**kwargs)
        else:
            response = client.chat.completions.create(**kwargs)
    except openai.APIError as e:
        raise _friendly(e) from e
    return (response.choices[0].message.content or "").strip()


def generate_json(system_prompt: str, user_prompt: str, *, name: str, max_tokens: int | None = None) -> Any:
    return parse_json(generate(system_prompt, user_prompt, name=name, json_mode=True, max_tokens=max_tokens))


async def stream(system_prompt: str, user_prompt: str, *, name: str) -> AsyncIterator[str]:
    client, model = _async_client()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=_messages(system_prompt, user_prompt),
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
            stream=True,
            name=name,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except openai.APIError as e:
        raise _friendly(e) from e


def parse_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating ```json fences or surrounding prose."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    raise LLMError("The model did not return valid JSON. Please try again.")
