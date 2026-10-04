# 💡 Lumina AI (v2.0)

> **A grounded, zero-hallucination AI research assistant.**  
> Upload scientific PDFs, ask questions answered *strictly* with page-level citations, generate 8 styles of summaries, create active-recall study sets, compare multiple papers, and spot hidden research gaps.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Qdrant](https://img.shields.io/badge/Vector_DB-Qdrant-dc2626.svg)](https://qdrant.tech/)
[![Free Tier Ready](https://img.shields.io/badge/Free_Tier-100%25_Supported-success.svg)](#-step-2-get-your-free-api-keys)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🌟 What is Lumina AI?

Reading complex academic papers is time-consuming. Generic AI chatbots often hallucinate facts, make up plausible-sounding citations, or fail to explain dense methodologies.

**Lumina AI** fixes this using **Retrieval-Augmented Generation (RAG)**:
- **Zero Hallucinations**: Answers are generated **only** from the actual text inside your uploaded papers. If something is not in the text, Lumina clearly states: *"I don't know"*.
- **Precise Page Citations**: Every statement is tagged with clickable or superscript references (e.g. `[1]`, `[2]`), indicating the exact paper, section, and page number.
- **100% Free-Tier Architecture**: Built to run completely on generous free tiers — **Groq** (Llama 3.3 70B) or **Google Gemini** for LLMs, **Jina AI** for semantic embeddings, and **Qdrant** for vector search. No expensive GPU or paid subscriptions required!

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 💬 **Grounded Q&A** | Chat with an individual paper or search your entire library at once. Supports real-time streaming responses with instant citation badges. |
| 📑 **8 Summary Modes** | Choose from: **Abstract**, **Methodology**, **Results**, **Conclusion**, **Beginner (ELI5)**, **Technical**, **Bullet Points**, or **One-Page Executive Brief**. |
| 🎓 **Interactive Quizzes** | Test your comprehension with auto-generated **Multiple Choice (MCQ)**, **True/False**, or **Short Answer** questions with explanations and instant scoring. |
| 🗂️ **Active-Recall Flashcards** | Digital flip cards generated directly from paper concepts for study and exam revision. |
| 🔬 **Research Gap Detector** | Automatically analyzes papers to reveal unaddressed limitations, assumptions, open problems, and promising future research ideas. |
| ⚖️ **Paper Comparison** | Select two or more papers to generate a side-by-side comparative analysis of problem statements, methods, datasets, and benchmark results. |
| 📊 **Modern Glassmorphic UI** | Responsive web dashboard with dark mode, system health monitors, paper library manager, and activity logs. |
| 🔭 **Full Observability** | Optional one-click integration with **Langfuse Cloud** to inspect retrieval relevance scores, token usage, latency, and prompts. |
| 🔒 **Access Gatekeeper** | Optional password protection (`ACCESS_CODE`) to keep your hosted app private. |

---

## 🧠 How It Works (In Plain English)

Lumina AI processes documents in two straightforward pipelines:

```
📄 1. WHEN YOU UPLOAD A PAPER (Indexing Pipeline)
   [Your PDF] 
       │
       ▼ PyMuPDF (Extracts text, strips messy headers/footers, extracts title & abstract)
   [Clean Text] 
       │
       ▼ Recursive Chunker (Splits text into 400-token chunks with 15% overlap)
   [Document Chunks] 
       │
       ▼ Jina AI Embeddings (Converts text chunks into mathematical vectors)
   [Qdrant Vector DB] (Stored with paper ID, page number, and section metadata)
```

```
🔍 2. WHEN YOU ASK A QUESTION (Query Pipeline)
   [Your Question] 
       │
       ▼ Jina AI Embeddings (Converts your question into a search vector)
   [Vector Search in Qdrant] (Finds top-5 most relevant chunks from the paper)
       │
       ▼ Context Injection (Numbers each excerpt with paper name, page, and section)
   [LLM: Groq / Gemini] (Instructed to answer strictly using the provided excerpts)
       │
       ▼
   [Cited Answer with [1], [2] References]
```

---

## 🚀 Beginner's Quickstart Guide

Get Lumina AI up and running locally in under 5 minutes.

### 📋 Prerequisites

Before starting, make sure you have:
1. **Python 3.11 or newer** installed ([Download Python](https://www.python.org/downloads/))
2. **Git** installed ([Download Git](https://git-scm.com/))
3. **Docker Desktop** installed & running ([Download Docker](https://www.docker.com/products/docker-desktop/))  
   *(Prefer not to use Docker? See the [No-Docker Alternative](#-alternative-running-without-local-docker) below!)*

---

### Step 1: Clone the Repository

Open your terminal (PowerShell, Command Prompt, or Terminal) and run:

```bash
git clone https://github.com/bandarilokesh/luminaai.git
cd luminaai
```

---

### Step 2: Get Your Free API Keys

You only need **two free keys** to get started:

1. **LLM Provider (Choose one)**:
   - **Groq** *(Recommended — blazing fast)*: Sign up and create a free key at [console.groq.com/keys](https://console.groq.com/keys).
   - **Google Gemini**: Grab a free Gemini API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

2. **Embeddings**:
   - **Jina AI**: Sign up for free (1 Million free tokens) at [jina.ai/embeddings](https://jina.ai/embeddings).

3. *(Optional)* **Observability**:
   - **Langfuse Cloud**: If you want live tracing and monitoring of your LLM calls, create a free project at [cloud.langfuse.com](https://cloud.langfuse.com).

---

### Step 3: Create Your `.env` File

Copy the template file to create your active configuration:

- **Windows (PowerShell / CMD)**:
  ```powershell
  copy .env.example .env
  ```
- **macOS / Linux**:
  ```bash
  cp .env.example .env
  ```

Open the new `.env` file in your favorite text editor (VS Code, Notepad, etc.) and paste your keys:

```ini
# Choose your LLM: "groq" or "gemini"
LLM_PROVIDER=groq

# If using Groq:
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# If using Gemini:
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=your_gemini_api_key_here
# GEMINI_MODEL=gemini-flash-lite-latest

# Embeddings API Key (Required)
JINA_API_KEY=jina_your_jina_api_key_here

# Local Vector Database (keep as default)
QDRANT_URL=http://localhost:6333
```

---

### Step 4: Start the Qdrant Vector Database

Start the Qdrant vector database container with one command:

```bash
docker compose up -d qdrant
```

> 💡 **Tip**: You can view the visual Qdrant dashboard anytime in your browser at: [http://localhost:6333/dashboard](http://localhost:6333/dashboard).

---

### Step 5: Install Dependencies & Run Lumina AI

Create a virtual environment and start the web server:

#### On Windows:
```powershell
# 1. Create a virtual environment
python -m venv .venv

# 2. Activate it
.venv\Scripts\activate

# 3. Install required packages
pip install -r requirements.txt

# 4. Start the app
uvicorn app.main:app --port 8000 --reload
```

#### On macOS / Linux:
```bash
# 1. Create a virtual environment
python3 -m venv .venv

# 2. Activate it
source .venv/bin/activate

# 3. Install required packages
pip install -r requirements.txt

# 4. Start the app
uvicorn app.main:app --port 8000 --reload
```

---

### Step 6: Open the App!

Open your browser and navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

1. Navigate to the **Upload** tab.
2. Drop in any PDF research paper (e.g., an arXiv paper).
3. Wait a few seconds for the status to switch to **Completed**.
4. Head over to **QA**, **Summary**, or **Study Tools** and start exploring!

---

## 🐳 Alternative: Run the Entire Stack in Docker

If you prefer to run both the app and the vector store inside Docker without installing Python locally:

```bash
# Build and run everything in the background
docker compose --profile app up -d --build
```

Then visit **[http://localhost:8000](http://localhost:8000)**.

To stop the containers:
```bash
docker compose --profile app down
```

---

## ☁️ Alternative: Running Without Local Docker

If you cannot install Docker on your machine, you can use **Qdrant Cloud's permanent free cluster**:

1. Sign up for free at [cloud.qdrant.io](https://cloud.qdrant.io).
2. Create a free 1GB cluster.
3. Copy your cluster URL and API key into your `.env`:
   ```ini
   QDRANT_URL=https://your-cluster-id.region.gcp.cloud.qdrant.io:6333
   QDRANT_API_KEY=your_qdrant_api_key
   ```
4. Run the Python app with `uvicorn app.main:app --port 8000` — no Docker required!

---

## 🧭 Navigating the App

| Tab | Purpose |
|---|---|
| **Dashboard** | Overview of your papers, question history, total study sessions, and live service health indicators. |
| **Library** | View all uploaded papers, metadata (authors, abstract, page counts, chunk count), or delete/re-index documents. |
| **Upload** | Drag-and-drop PDF papers into the indexing engine (up to 50MB per paper). |
| **QA (Chat)** | Ask questions with streaming responses, page-level citation pills, and source excerpts. Filter by specific papers or search your entire library. |
| **Summary** | Generate targeted summaries in 8 distinct formats (Abstract, ELI5 Beginner, Technical, Bullet points, etc.) with markdown export. |
| **Study Tools** | Generate custom **Quizzes** (MCQ, True/False, Short Answer) or interactive **Flashcards** for exam preparation. |
| **Research Gaps** | Detect limitations, unsupported assumptions, and open research directions across one or more papers. |
| **Compare** | Compare 2+ papers side-by-side to understand differing methodologies and benchmark performances. |
| **Settings** | Inspect API connectivity for Groq/Gemini, Jina AI, Qdrant, and Langfuse. |

---

## ⚙️ Configuration Reference

All settings can be tweaked inside your `.env` file:

| Variable | Default Value | Explanation |
|---|---|---|
| `LLM_PROVIDER` | `groq` | Choose which LLM provider to use (`groq` or `gemini`). |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq chat model identifier. |
| `GEMINI_MODEL` | `gemini-flash-lite-latest` | Gemini chat model identifier. |
| `TEMPERATURE` | `0.2` | Creativity level (keep low ~0.2 for strict academic accuracy). |
| `MAX_TOKENS` | `2048` | Maximum length of LLM responses. |
| `EMBEDDING_MODEL` | `jina-embeddings-v3` | Embedding model used for vectorization. |
| `EMBEDDING_DIM` | `1024` | Vector dimension size (must match embedding model). |
| `QDRANT_URL` | `http://localhost:6333` | Address of your Qdrant instance. |
| `CHUNK_SIZE` | `400` | Target size of each chunk in tokens. |
| `CHUNK_OVERLAP` | `60` | Token overlap between consecutive chunks (15%). |
| `TOP_K` | `5` | Number of relevant chunks retrieved per question. |
| `CONTEXT_TOKEN_BUDGET`| `6000` | Maximum context tokens sent to LLM to prevent hitting free rate limits. |
| `ACCESS_CODE` | `""` *(blank)* | Optional master password required to access the UI and API. |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum allowed PDF upload size in megabytes. |

---

## 🛠️ REST API Documentation

Lumina AI includes an interactive Swagger / OpenAPI interface. With the server running, visit:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

### Key Endpoints:
- `POST /api/papers/upload` — Upload and index a new PDF paper.
- `GET /api/papers/` — List all papers and their indexing statuses.
- `DELETE /api/papers/{id}` — Delete a paper and remove its vectors from Qdrant.
- `POST /api/qa` — Submit a question and receive a cited response.
- `POST /api/qa/stream` — Real-time Server-Sent Events (SSE) question answering.
- `POST /api/summary` — Request a summary in any of the 8 supported styles.
- `POST /api/quiz` — Generate an active recall quiz.
- `POST /api/flashcards` — Generate study flashcards.
- `POST /api/compare` — Compare two or more papers.
- `POST /api/gap-detector` — Detect unaddressed research gaps.
- `GET /api/status` — Get connectivity status of all backend services.

---

## 🧪 Running Tests

Lumina AI comes with an automated test suite verifying both API endpoints and the RAG logic.

Tests run **100% offline** without needing Docker or making external API calls: Qdrant runs in in-memory mode, and the LLM and embedding models use deterministic mocks.

```bash
# Run all tests using pytest
pytest
```

*(You should see `15 passed` in a few seconds).*

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><b>1. Why does Lumina say "I don't know"?</b></summary>
This is by design! Lumina AI is built for strict academic honesty. If your question cannot be substantiated by the retrieved excerpts from your uploaded papers, it refuses to guess or invent details.
</details>

<details>
<summary><b>2. Can I upload scanned PDFs?</b></summary>
Lumina extracts text using PyMuPDF and does not currently include Optical Character Recognition (OCR). If your PDF consists of scanned photo pages where text cannot be selected or copied, you will need to run OCR first (e.g. using Adobe Acrobat or OCRmyPDF).
</details>

<details>
<summary><b>3. What does error "Rate limit reached (429)" mean?</b></summary>
Free-tier API providers (like Groq or Gemini) impose per-minute request limits. If you ask many questions in quick succession, wait 30–60 seconds. You can also easily toggle between Groq and Gemini in your <code>.env</code>.
</details>

<details>
<summary><b>4. How do I put a password on my deployment?</b></summary>
Set <code>ACCESS_CODE=yourSecretPassword</code> in your <code>.env</code> file. Anyone accessing the web UI or API will be prompted to enter this password.
</details>

<details>
<summary><b>5. Where are my papers and metadata stored?</b></summary>
- PDF files: Saved in the local <code>uploads/</code> directory.
- SQLite database: Stored at <code>data/lumina.db</code> (keeps paper titles, summaries, and history).
- Vector embeddings: Stored in Qdrant (either in the Docker volume <code>qdrant_data</code> or your Qdrant Cloud cluster).
</details>

---

## 📁 Project Structure

```
lumina-ai/
├── app/
│   ├── config.py             # Settings, paths, and environment variable parsing
│   ├── db.py                 # SQLite database storage (papers, history, activity)
│   ├── features.py           # Summaries, quizzes, flashcards, comparison, gaps
│   ├── logger.py             # Colorized application logger
│   ├── main.py               # FastAPI entrypoint, lifespan, auth gate & routing
│   ├── observability.py      # Langfuse tracing integrations
│   ├── schemas.py            # Pydantic data schemas for requests and responses
│   ├── rag/
│   │   ├── chunker.py        # Recursive token-aware text chunking
│   │   ├── embeddings.py     # Jina AI embedding client
│   │   ├── llm.py            # Groq & Gemini OpenAI-compatible client
│   │   ├── loader.py         # PyMuPDF text cleaner and metadata extractor
│   │   ├── pipeline.py       # Core RAG indexing and QA answering logic
│   │   ├── prompts.py        # System prompts and templates
│   │   ├── retriever.py      # Cosine similarity vector search
│   │   └── vector_store.py   # Qdrant client collection management
│   └── routers/
│       ├── papers.py         # Paper upload, deletion, listing, re-indexing
│       └── rag.py            # QA, summary, study tools, comparison endpoints
├── frontend/
│   └── static/               # Single-page web application (HTML, CSS, JS)
├── tests/
│   ├── test_api.py           # FastAPI endpoint tests
│   └── test_rag.py           # Chunker, retriever, and pipeline tests
├── docker-compose.yml        # Docker definitions for Qdrant and the Web App
├── Dockerfile                # Multi-stage container build
├── requirements.txt          # Python dependencies
└── .env.example              # Environment variables template
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) — feel free to use, modify, and distribute it for academic or personal projects.
