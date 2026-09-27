# Lumina AI

A Retrieval-Augmented Generation (RAG) research assistant. Upload PDF papers, ask questions answered **only** from
those papers (with citations), and generate summaries, quizzes, flashcards, comparisons and research-gap reports.

Everything runs on free tiers: **Groq** or **Gemini** for the LLM, **Jina AI** for embeddings, **Qdrant** (Docker)
as the vector database and **Langfuse Cloud** for observability. No local models are downloaded.

## How it works

**Indexing pipeline** (once per paper)

```
PDF -> Loader -> Cleaning -> Recursive Chunker -> Jina embeddings -> Qdrant (ID + vector + payload)
```

| Step | File | What it does |
|---|---|---|
| Loader | [app/rag/loader.py](app/rag/loader.py) | PyMuPDF text per page; removes repeated headers/footers and page numbers, fixes hyphenation, normalizes text; extracts title, authors, abstract and section headings (metadata). |
| Chunker | [app/rag/chunker.py](app/rag/chunker.py) | Recursive chunking (paragraph → line → sentence → word), 400 tokens with 60 overlap (15%). Each chunk keeps page and section. |
| Embedding model | [app/rag/embeddings.py](app/rag/embeddings.py) | `jina-embeddings-v3`, normalized vectors. Same model for documents (`retrieval.passage`) and queries (`retrieval.query`). |
| Vector database | [app/rag/vector_store.py](app/rag/vector_store.py) | Qdrant collection with cosine distance; `create_collection`, `upsert`, `query_points`, `delete`, `get_collection`; payload index on `paper_id` for metadata filtering. |

**Query pipeline** (every question)

```
Question -> query embedding -> Retriever (top-k, filtered by paper) -> context injection -> LLM -> cited answer
```

| Step | File | What it does |
|---|---|---|
| Retriever | [app/rag/retriever.py](app/rag/retriever.py) | Semantic (dense) search in Qdrant, top-5 by cosine similarity. |
| Prompt augmentation | [app/rag/prompts.py](app/rag/prompts.py) | System prompt + prompt template; retrieved chunks injected as numbered context. Grounded generation: *answer only from the context, otherwise say "I don't know"*. |
| LLM | [app/rag/llm.py](app/rag/llm.py) | Groq or Gemini via their OpenAI-compatible APIs. |
| Pipelines | [app/rag/pipeline.py](app/rag/pipeline.py) | `index_paper`, `answer_question`, `stream_answer`. |
| Features | [app/features.py](app/features.py) | Summaries (8 styles), quiz, flashcards, comparison, research gaps — all built on retrieved context. |

**Observability**: every request is traced in Langfuse — retrieval (with scores), embedding calls (token usage) and
each LLM generation (prompt, output, tokens, latency). See [app/observability.py](app/observability.py).

## Setup

Prerequisites: Python 3.11+, Docker Desktop.

1. **Get free API keys**
   - LLM, one of: Groq — <https://console.groq.com/keys>, or Gemini — <https://aistudio.google.com/apikey>
   - Embeddings: Jina AI — <https://jina.ai/embeddings>
   - Observability (optional): Langfuse — <https://cloud.langfuse.com> → create a project → Settings → API Keys

2. **Configure**
   ```bash
   copy .env.example .env      # macOS/Linux: cp .env.example .env
   ```
   Fill in `LLM_PROVIDER` (`groq` or `gemini`), the matching API key, `JINA_API_KEY`, and optionally the
   `LANGFUSE_*` keys.

3. **Start Qdrant**
   ```bash
   docker compose up -d qdrant
   ```
   Dashboard: <http://localhost:6333/dashboard>

4. **Install and run**
   ```bash
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt          # macOS/Linux: .venv/bin/pip ...
   .venv\Scripts\uvicorn app.main:app --port 8000
   ```
   Open <http://localhost:8000>. The Settings page shows whether Qdrant, the LLM, Jina and Langfuse are connected.

To run the whole stack in Docker instead: `docker compose --profile app up -d --build`.

## Configuration

All settings live in `.env` (see [.env.example](.env.example)).

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq` or `gemini` |
| `GROQ_MODEL` / `GEMINI_MODEL` | `llama-3.3-70b-versatile` / `gemini-flash-lite-latest` | Any chat model the provider offers |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | `jina-embeddings-v3` / `1024` | Changing the dimension needs a new `QDRANT_COLLECTION` |
| `QDRANT_URL` | `http://localhost:6333` | Also works with a Qdrant Cloud URL + `QDRANT_API_KEY` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `400` / `60` | Tokens |
| `TOP_K` | `5` | Chunks retrieved per question |
| `CONTEXT_TOKEN_BUDGET` | `6000` | Keeps prompts within free-tier rate limits |
| `ACCESS_CODE` | blank | Optional password for the whole app |

## API

Interactive docs at <http://localhost:8000/docs>. Main endpoints:

- `POST /api/papers/upload`, `GET /api/papers/`, `DELETE /api/papers/{id}`, `POST /api/papers/{id}/reindex`
- `POST /api/qa` and `POST /api/qa/stream` (server-sent events) — `paper_ids: []` searches the whole library
- `POST /api/summary`, `/api/quiz`, `/api/flashcards`, `/api/compare`, `/api/gap-detector`
- `GET /api/status`, `/api/stats`, `/api/activity`

## Tests

```bash
.venv\Scripts\python -m pytest
```

Tests run offline: Qdrant runs in in-memory mode and the embedding model and LLM are replaced with deterministic fakes.

## Limitations

- Scanned (image-only) PDFs are not supported — there is no OCR.
- Retrieval is semantic only; exact-keyword lookups (IDs, rare acronyms) can be missed.
- Free tiers have rate limits; a 429 error shows as "rate limit reached, retry in a minute".
