# PaperMind AI: Local RAG Research Paper Summarizer & QA Assistant

An enterprise-grade, offline-capable desktop application designed for indexing, reading, summarizing, and testing comprehension of research papers. Operating 100% locally on your machine, it guarantees complete data privacy and requires no paid APIs (no OpenAI, Gemini, or Claude keys).

---

## Key Features

- **Local PDF Processing & OCR:** Layout-aware column sorting for academic PDFs (prevents garbling of two-column articles) using PyMuPDF and pdfplumber, with pytesseract OCR fallback for scanned papers.
- **Adaptive Heading Chunker:** Automatically splits documents based on section headings (e.g. Introduction, Methodology, Results) rather than arbitrary fixed sizes.
- **Hybrid Dense/Sparse Retrieval:** Integrates BM25 lexical keyword search alongside SentenceTransformers vector embeddings (FAISS and ChromaDB support).
- **Cross-Encoder Re-ranking:** Re-scores retrieved candidate context chunks using Cross-Encoder models (`cross-encoder/ms-marco-MiniLM-L-6-v2`) for premium answer precision.
- **Factual citations & Guardrails:** Strict prompt templates prevent hallucinations. If context is missing, the AI returns a standard "insufficient evidence" statement. Citations list source paper name, page number, and section.
- **Academic Study tools:** Generate study flashcards, interactive quizzes (multiple-choice or short-answers) with difficulty levels, and automatic research gap/limitation detection.
- **Multi-Paper Analysis:** Upload and compare multiple papers at once. Compare datasets, methodologies, models, and performance metrics.
- **Local SQLite Caching:** Speeds up operations by caching computed embeddings and generated summary brief perspectives (Abstract, Methodology, Results, Conclusion, Technical, ELI5).

---

## System Architecture

The project adheres to Clean Architecture principles to ensure modularity and ease of extension:

- **Presentation Layer (`frontend/`):** Streamlit GUI dashboard, library views, interactive QA chat interface, quiz templates, and system hardware status (CUDA/CPU).
- **Orchestration Layer (`backend/`):** FastAPI endpoints managing file upload streams, database logging, background workers, and study tools requests.
- **RAG Engine (`rag/`):** Column-sorting PDF reader, heading chunker, dense/sparse search mergers, and re-ranking algorithms.
- **Infrastructure & Storage (`database/`, `cache/`):** SQLite database helper storing paper records and summaries cache; FAISS/Chroma database files saving vector index arrays.
- **Model Interfaces (`models/`):** System prompt orchestrators and local LLM connectors (Ollama REST client).

---

## Installation & Setup

### Prerequisites

1. **Python 3.12.x** installed.
2. **Ollama** installed on your system. Download it from [Ollama.com](https://ollama.com).
3. Pull the default local models you wish to use:
   ```bash
   ollama pull llama3.2
   ollama pull qwen2.5
   ```
4. (Optional) **Tesseract OCR** binary installed on host system for scanned PDF OCR support.

### Local Setup

1. **Clone the Repository and Navigate to Root:**
   ```bash
   cd c:\PaperMind-Ai
   ```

2. **Initialize Virtual Environment & Install Dependencies:**
   ```bash
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

3. **Set Up environment Configurations:**
   Copy `.env.example` to `.env` and customize parameters if desired (e.g. adjust chunk parameters, vector store backend type):
   ```bash
   copy .env.example .env
   ```

4. **Launch Backend API (FastAPI):**
   ```bash
   .venv\Scripts\uvicorn backend.main:app --reload --port 8000
   ```

5. **Launch Frontend GUI (Streamlit):**
   ```bash
   .venv\Scripts\streamlit run frontend/app.py
   ```
   Open `http://localhost:8501` in your browser.

---

## Running inside Docker

A `Dockerfile` and `docker-compose.yml` are provided to run the services in isolated containers. Docker Compose automatically forwards Ollama requests to the host machine.

1. **Build and Start Container Services:**
   ```bash
   docker-compose up --build
   ```

2. Access the Streamlit UI at `http://localhost:8501` and FastAPI docs at `http://localhost:8000/docs`.

---

## Running Tests & Evaluations

Run the complete test suite (unit and integration tests) using Pytest:

```bash
.venv\Scripts\pytest tests/
```

- **`tests/test_pdf.py`**: Validates PDF cleanup and columns-sorting reading order.
- **`tests/test_retrieval.py`**: Verifies BM25 rank calculations, ROUGE metric functions, precision/recall MRR solvers, and citation parser validity.
- **`tests/test_api.py`**: Integrates test clients to verify backend endpoints health and response codes.
