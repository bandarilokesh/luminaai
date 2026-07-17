# Lumina Ai: Local RAG Research Paper Summarizer & QA Assistant

An enterprise-grade desktop application designed for indexing, reading, summarizing, and testing comprehension of research papers. It uses Gemini API for fast LLM inference.

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

- **Presentation Layer (`frontend/`):** Vanilla JS/HTML SPA dashboard, library views, interactive QA chat interface, quiz templates.
- **Orchestration Layer (`backend/`):** FastAPI endpoints managing file upload streams, database logging, background workers, study tools requests, and serving the frontend static files.
- **RAG Engine (`rag/`):** Column-sorting PDF reader, heading chunker, dense/sparse search mergers, and re-ranking algorithms.
- **Infrastructure & Storage (`database/`, `cache/`):** SQLite database helper storing paper records and summaries cache; FAISS/Chroma database files saving vector index arrays.
- **Model Interfaces (`models/`):** System prompt orchestrators and Gemini API connector (`services/gemini_client.py`).

---

## Installation & Setup

### Prerequisites

1. **Python 3.12.x** installed.
2. **Gemini API Key:** You need a valid Gemini API key from Google AI Studio.
3. (Optional) **Tesseract OCR** binary installed on host system for scanned PDF OCR support.

### Local Setup

1. **Clone the Repository and Navigate to Root:**
   ```bash
   cd c:\Lumina-Ai
   ```

2. **Initialize Virtual Environment & Install Dependencies:**
   ```bash
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

3. **Set Up environment Configurations:**
   Copy `.env.example` to `.env` and configure your API key:
   ```bash
   copy .env.example .env
   ```
   Open `.env` and set `GEMINI_API_KEY=<your_api_key>`

4. **Launch Backend API (FastAPI):**
   ```bash
   .venv\Scripts\uvicorn backend.main:app --reload --port 8000
   ```

5. **Access the Application:**
   Open `http://localhost:8000` in your browser. The backend FastAPI server automatically serves the frontend static SPA.

---

## Running inside Docker

A `Dockerfile` and `docker-compose.yml` are provided to run the services in isolated containers. Ensure you pass your Gemini API key in `.env`.

1. **Build and Start Container Services:**
   ```bash
   docker-compose up --build
   ```

2. Access the Application UI at `http://localhost:8000` and FastAPI docs at `http://localhost:8000/docs`.

---

## Running Tests & Evaluations

Run the complete test suite (unit and integration tests) using Pytest:

```bash
.venv\Scripts\pytest tests/
```

- **`tests/test_pdf.py`**: Validates PDF cleanup and columns-sorting reading order.
- **`tests/test_retrieval.py`**: Verifies BM25 rank calculations, ROUGE metric functions, precision/recall MRR solvers, and citation parser validity.
- **`tests/test_api.py`**: Integrates test clients to verify backend endpoints health and response codes.
