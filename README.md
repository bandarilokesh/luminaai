# Lumina AI 🧠

Welcome to **Lumina AI**! This is a complete, beginner-friendly guide to understanding, installing, and using your very own local Research Assistant powered by Retrieval-Augmented Generation (RAG) and Google's Gemini AI.

---

## 🌟 What is Lumina AI?

Have you ever had to read a 30-page academic paper and wished you could just "talk" to it? That's what Lumina AI does! 

It is an enterprise-grade desktop web application that allows you to:
- **Upload** complex PDF research papers.
- **Summarize** them instantly in different styles (Abstract, ELI5, Technical).
- **Ask Questions** and get answers directly sourced and cited from the uploaded documents, verified against hallucinations.
- **Generate Study Tools** like flashcards and multiple-choice quizzes to test your comprehension.
- **Visualize** relationships through automatically generated Knowledge Graphs.
- **Detect Gaps & Contradictions** across a corpus using AI Research Agents.
- **Fully Offline Capable**: Use Google Gemini for speed, or swap to Ollama to keep everything 100% local and private.

---

## 🏗️ How Does it Work? (The Architecture)

Lumina AI uses a modern **Clean Architecture** to keep the code organized and easy to understand:

1. **The Frontend (UI):** Built entirely with pure HTML, CSS, and JavaScript. It features a trendy, matte, image-based design system with a floating sidebar and dynamic content rendering. No complex frameworks like React or Tailwind are required!
2. **The Backend (API):** Powered by **FastAPI** (Python). This handles all the heavy lifting, routing your requests, and serving the beautiful user interface.
3. **The RAG Engine:** "RAG" stands for Retrieval-Augmented Generation. When you upload a PDF, this engine reads it, breaks it down into small logical chunks, and saves those chunks into a Vector Database. When you ask a question, it searches for the most relevant chunks and sends them to the AI so the AI can answer accurately without guessing (hallucinating).
4. **The AI Connectors:** Connects securely to Google's Gemini models using the modern `google-genai` SDK to generate summaries and answers.

---

## 🚀 Getting Started

Follow these simple steps to get Lumina AI running on your computer.

### Prerequisites
- **Python 3.12+** installed on your machine.
- A **Gemini API Key**. You can get one for free from [Google AI Studio](https://aistudio.google.com/).

### Step-by-Step Installation

1. **Clone the Repository:**
   Open your terminal/command prompt and run:
   ```bash
   git clone https://github.com/bandarilokesh/PaperMind-Ai.git
   cd PaperMind-Ai
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
   The project needs your Gemini API key to work. 
   - Copy the `.env.example` file and rename it to `.env`.
   - Open the `.env` file in any text editor and paste your API key:
     ```env
     GEMINI_API_KEY=your_actual_api_key_here
     ```

5. **Start the Application!**
   Run the FastAPI server:
   - On **Windows**:
     ```bash
     .venv\Scripts\uvicorn backend.main:app --reload --port 8000
     ```
   - On **Mac/Linux**:
     ```bash
     uvicorn backend.main:app --reload --port 8000
     ```

6. **Open the App:**
   Open your web browser and go to **[http://localhost:8000](http://localhost:8000)**. You will see the Lumina AI dashboard!

---

## 🐳 Running with Docker (Alternative)

If you prefer using Docker, it's incredibly easy! Just make sure your `.env` file is set up with your API key, then run:

```bash
docker-compose up --build
```
This will start both Lumina AI and a local Ollama instance (for fully offline inference). The application will be available at `http://localhost:8000`.

---

## 🎨 A Tour of the Application

- **Dashboard:** The main landing page. Use the "Quick Upload" button to add new PDF papers to your local library.
- **Library:** View all the papers you have uploaded. 
- **QA (Question & Answer):** Select a paper and ask questions about it. The AI will provide cited answers!
- **Summary:** Get automated summaries of your papers. Choose from different perspectives like "Methodology" or "ELI5" (Explain Like I'm 5).
- **Knowledge Graph:** See the extracted methods, datasets, and entities mapped out across your research library.
- **Compare Papers:** Generate a structured Markdown comparison table analyzing multiple papers side-by-side.
- **Research Gaps:** Let the AI act as a peer reviewer to detect missing experiments and contradictions across a corpus.

---

## 🛠️ Troubleshooting for Beginners

- **Error: 404 models/gemini-1.5-flash is not found:** Ensure you are using the latest `google-genai` SDK and not the deprecated `google-generativeai` library. Lumina AI has already been updated to use the correct library!
- **Port 8000 is in use:** If the server won't start because the port is busy, you can change the port by running: `uvicorn backend.main:app --reload --port 8080` (and then visit `http://localhost:8080`).

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
