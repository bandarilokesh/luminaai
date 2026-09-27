"""Embedding model: Jina AI embeddings API.

The same model embeds documents and queries so both live in the same vector space. Jina's
`task` parameter adds the matching retrieval adapter (passage vs. query). Vectors are returned
normalized to unit length, which suits cosine similarity search.
"""
import time

import httpx

from app.config import settings
from app.logger import logger
from app.observability import langfuse, observe

_RETRY_STATUS = {429, 500, 502, 503, 504}


class EmbeddingError(RuntimeError):
    pass


class JinaEmbeddings:
    def __init__(self, api_key: str = settings.JINA_API_KEY, model: str = settings.EMBEDDING_MODEL):
        self.api_key = api_key
        self.model = model
        self._http = httpx.Client(timeout=60)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _request(self, texts: list[str], task: str) -> tuple[list[list[float]], int]:
        if not self.is_configured():
            raise EmbeddingError("JINA_API_KEY is not set. Get a free key at https://jina.ai/embeddings")
        payload = {
            "model": self.model,
            "task": task,
            "input": texts,
            "dimensions": settings.EMBEDDING_DIM,
            "normalized": True,
            "embedding_type": "float",
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for attempt in range(5):
            try:
                response = self._http.post(settings.EMBEDDING_URL, json=payload, headers=headers)
            except httpx.HTTPError as e:
                if attempt == 4:
                    raise EmbeddingError(f"Could not reach Jina embeddings API: {e}") from e
                time.sleep(2 ** attempt)
                continue
            if response.status_code in _RETRY_STATUS and attempt < 4:
                wait = float(response.headers.get("retry-after", 2 ** attempt))
                logger.warning(f"Jina API returned {response.status_code}; retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
            if response.status_code != 200:
                raise EmbeddingError(f"Jina embeddings API error {response.status_code}: {response.text[:300]}")
            body = response.json()
            data = sorted(body["data"], key=lambda d: d["index"])
            return [d["embedding"] for d in data], body.get("usage", {}).get("total_tokens", 0)
        raise EmbeddingError("Jina embeddings API retries exhausted")

    @observe(name="embed-documents", as_type="embedding", capture_input=False, capture_output=False)
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        tokens = 0
        size = settings.EMBEDDING_BATCH_SIZE
        for start in range(0, len(texts), size):
            batch, used = self._request(texts[start:start + size], task="retrieval.passage")
            vectors.extend(batch)
            tokens += used
        langfuse.update_current_generation(
            model=self.model, usage_details={"input": tokens}, metadata={"texts": len(texts)}
        )
        return vectors

    @observe(name="embed-query", as_type="embedding", capture_output=False)
    def embed_query(self, text: str) -> list[float]:
        vectors, tokens = self._request([text], task="retrieval.query")
        langfuse.update_current_generation(model=self.model, usage_details={"input": tokens})
        return vectors[0]


embeddings = JinaEmbeddings()
