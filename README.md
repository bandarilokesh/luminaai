# Lumina AI 🧠

Welcome to **Lumina AI**! This is a complete, beginner-friendly guide to understanding, installing, and using your very own local Research Assistant powered by Retrieval-Augmented Generation (RAG) and Google's Gemini AI.

---

## 🌟 What is Lumina AI?

Have you ever had to read a 30-page academic paper and wished you could just "talk" to it? That's what Lumina AI does!

It is an enterprise-grade desktop web application that allows you to:
- **Upload** complex PDF research papers (including scanned/image-based PDFs via optional OCR).
- **Summarize** them instantly in different styles — Abstract, Methodology, Results, Conclusion, ELI5 ("Explain Like I'm 5"), Technical, and Bullet-point briefs.
- **Ask Questions** and get answers directly sourced and cited from the uploaded documents, either as a normal response or streamed live over a WebSocket.
- **Verify every answer** through an automated pipeline that decomposes claims, checks them against the retrieved evidence, validates citation accuracy, and attaches a confidence score — so you know when to trust it.
- **Generate Study Tools** like flashcards and multiple-choice quizzes to test your comprehension.
- **Visualize** relationships through automatically generated Knowledge Graphs of methods, datasets, and entities.
- **Detect Research Gaps** — an AI research agent reviews your corpus for limitations, missing experiments, and contradictions.
- **Compare Papers** side-by-side in a structured Markdown table.
- **Fully Offline Capable**: Use Google Gemini for speed, or switch the `LLM_PROVIDER` to Ollama to keep everything 100% local and private.
- **Optional Access Code**: gate the whole app behind a shared password if you ever expose it beyond your own machine.

---

## 🏗️ How Does it Work? (The Architecture)

Lumina AI uses a modern **Clean Architecture** to keep the code organized and easy to understand:

1. **The Frontend (UI):** Built entirely with pure HTML, CSS, and JavaScript. It features a trendy, matte, image-based design system with a floating sidebar and dynamic content rendering. No complex frameworks like React or Tailwind are required!
2. **The Backend (API):** Powered by **FastAPI** (Python). This handles all the heavy lifting, routing your requests, and serving the user interface.
3. **The RAG Engine:** When you upload a PDF, it's parsed (text, tables, and sections classified) and split with a hierarchical chunker. Chunks are indexed into both a **dense vector store** (FAISS/Chroma with sentence-transformer embeddings) and a **sparse BM25 index**; at query time both are searched and fused, then a cross-encoder reranks the results before they're handed to the LLM.
4. **The Verification Pipeline:** Before an answer reaches you, it's decomposed into individual claims, each claim is checked against the retrieved evidence, citation markers are validated against the actual source chunks, and a final confidence score is computed.
5. **The AI Connectors:** Connects securely to Google's Gemini models using the modern `google-genai` SDK, with an optional switch to a local Ollama instance for fully offline inference.

---

## 🚀 Getting Started

Follow these simple steps to get Lumina AI running on your computer.

### Prerequisites
- **Python 3.12+** installed on your machine.
- A **Gemini API Key** (free from [Google AI Studio](https://aistudio.google.com/)) — unless you plan to run entirely on **Ollama** instead (see Configuration below).
- *(Optional)* **Tesseract OCR** installed and on your `PATH` if you want to extract text from scanned/image-only PDFs. Without it, Lumina AI still works fine for normal (text-based) PDFs.

### Step-by-Step Installation

1. **Clone the Repository:**
   Open your terminal/command prompt and run:
   ```bash
   git clone https://github.com/bandarilokesh/luminaai.git
   cd luminaai
   ```

2. **Create a Virtual Environment:**
   This creates a safe, isolated space for the project's Python dependencies.
   ```bash
   python -m venv .venv
   ```

3. **Install Dependencies:**
   Activate the environment and install the required packages.
   - On **Windows**:
     ```bash
     .venv\Scripts\pip install -r requirements.txt
     ```
   - On **Mac/Linux**:
     ```bash
     source .venv/bin/activate
     pip install -r requirements.txt
     ```

4. **Set Up Your Environment Variables:**
   - Copy the `.env.example` file and rename it to `.env`.
   - Open the `.env` file in any text editor and paste your API key:
     ```env
     GEMINI_API_KEY=your_actual_api_key_here
     ```
   - See [Configuration](#-configuration) below for the other options available (Ollama, access code, chunking, retrieval, etc.).

5. **Start the Application!**
   - On **Windows**, either run the FastAPI server directly:
     ```bash
     .venv\Scripts\uvicorn backend.main:app --reload --port 8000
     ```
     ...or just double-click **`Start-Lumina-Ai.vbs`** — it launches the server with zero terminal windows and opens your browser automatically once it's ready. Double-click **`Stop-Lumina-Ai.vbs`** to shut it back down.
   - On **Mac/Linux**:
     ```bash
     uvicorn backend.main:app --reload --port 8000
     ```

6. **Open the App:**
   Open your web browser and go to **[http://localhost:8000](http://localhost:8000)**. You will see the Lumina AI dashboard!

---

## ⚙️ Configuration

All configuration lives in `.env` (copy it from `.env.example`). The most useful options:

| Variable | What it does |
|---|---|
| `GEMINI_API_KEY` | Your Google AI Studio key. Required unless `LLM_PROVIDER=ollama`. |
| `LLM_PROVIDER` | `gemini` (default) or `ollama` — switches every summary/QA/agent call to a local Ollama instance at `OLLAMA_API_URL`. |
| `MODEL_NAME` | Which model to call (e.g. `gemini-flash-lite-latest`, or an Ollama model tag). |
| `ACCESS_CODE` | Optional shared password. Leave blank for an open app; set it to require a login screen before anyone can use it. |
| `DEFAULT_EMBEDDING_MODEL` | Sentence-transformer model used for dense retrieval (e.g. `BAAI/bge-small-en-v1.5`). |
| `RERANK_MODEL` / `USE_RERANKER` | Cross-encoder reranker applied after hybrid retrieval. |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Controls the hierarchical chunker's target chunk size and overlap. |
| `TOP_K_DENSE` / `RERANK_TOP_N` | How many chunks are retrieved vs. kept after reranking. |

---

## 🎨 A Tour of the Application

- **Dashboard:** The main landing page. Use the "Quick Upload" button to add new PDF papers to your local library, and see recent activity at a glance.
- **Library:** View all the papers you have uploaded.
- **QA (Question & Answer):** Select a paper and ask questions about it. The AI provides cited, verified answers, streamed live as they're generated.
- **Summary:** Get automated summaries of your papers in multiple styles — Abstract, Methodology, Results, Conclusion, ELI5, Technical, or Bullet-point.
- **Flashcards & Quizzes:** Auto-generate study flashcards and multiple-choice quizzes from any paper.
- **Knowledge Graph:** See the extracted methods, datasets, and entities mapped out across your research library.
- **Compare Papers:** Generate a structured Markdown comparison table analyzing multiple papers side-by-side.
- **Research Gaps:** Let the AI act as a peer reviewer to detect missing experiments and contradictions across a corpus.

---

## 🛠️ Troubleshooting for Beginners

- **Error: 404 models/gemini-1.5-flash is not found:** Ensure you are using the latest `google-genai` SDK and not the deprecated `google-generativeai` library. Lumina AI has already been updated to use the correct library!
- **Port 8000 is in use:** If the server won't start because the port is busy, you can change the port by running: `uvicorn backend.main:app --reload --port 8080` (and then visit `http://localhost:8080`).
- **Scanned PDFs return little/no text:** Install Tesseract OCR and make sure it's on your system `PATH`. Without it, Lumina AI logs a warning and falls back to whatever text layer the PDF already has.

---

## 🧪 Running Tests

To ensure everything is working correctly under the hood, you can run the automated test suite:

- On **Windows**:
  ```bash
  .venv\Scripts\pytest tests/
  ```
- On **Mac/Linux**:
  ```bash
  pytest tests/
  ```

Happy Researching! 📚✨
