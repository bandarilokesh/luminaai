---
title: Lumina AI
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 8000
pinned: false
---

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

## 🌐 Deploy It for Free (So Anyone, Anywhere Can Use It)

Right now Lumina AI only runs on your own computer. This section walks you through putting it on the public internet, for free, using **Hugging Face Spaces** — chosen because it gives you a generous free tier (2 CPU cores, 16 GB RAM) that comfortably fits this app's AI models, needs no credit card, and builds straight from your existing `Dockerfile`.

> ⚠️ **Before you deploy:** this app has no login system, and it uses *your* Gemini API key on the server for every request. If you make it public without protection, strangers who find the link can use up your Gemini quota. Lumina AI now includes an optional **access code** gate for exactly this reason — set it in Step 4 below. Leave it blank only if you're fine with the app being 100% open.

### Step 1: Get your accounts ready
- A free [Hugging Face](https://huggingface.co/join) account.
- Your **Gemini API key** from [Google AI Studio](https://aistudio.google.com/) (same one you use locally).
- Make sure your latest code is pushed to your GitHub repo (`git push`), so nothing gets lost.

### Step 2: Create a new Space
1. Go to [huggingface.co/new-space](https://huggingface.co/new-space).
2. Give it a name (e.g. `lumina-ai`).
3. Under **Select the Space SDK**, choose **Docker** → **Blank**.
4. Choose the **CPU basic · Free** hardware tier.
5. Set visibility to **Public** (so anyone can open the link) and click **Create Space**.

### Step 3: Push your code to the Space
Hugging Face gives every Space its own git repository. Add it as a second remote alongside your existing GitHub `origin` and push to it:

```bash
git remote add space https://huggingface.co/spaces/<your-username>/<your-space-name>
git push space main
```

You'll be prompted for credentials — use your Hugging Face username and an [access token](https://huggingface.co/settings/tokens) (with "write" permission) as the password.

This repo's `README.md` already has the small YAML block at the top (`sdk: docker`, `app_port: 8000`) that tells the Space how to build it — you don't need to add anything for that part.

### Step 4: Add your secrets
Your `.env` file never gets pushed (it's git-ignored on purpose), so you set these in the Space's UI instead:

1. On your Space's page, go to **Settings → Variables and secrets**.
2. Add these as **Secrets** (hidden, encrypted):
   - `GEMINI_API_KEY` — your Gemini API key.
   - `ACCESS_CODE` — a password you make up, e.g. `letmein-2026`. Share this only with people you want using the app. Leave it out entirely if you want the app fully open.
3. (Optional) Add these as plain **Variables** if you want lighter, faster models — recommended on the free tier so the app starts up quickly:
   - `DEFAULT_EMBEDDING_MODEL` = `BAAI/bge-small-en-v1.5`
   - `RERANK_MODEL` = `cross-encoder/ms-marco-MiniLM-L-6-v2`

### Step 5: Wait for the build, then open it
- The Space will automatically start building your Docker image — you can watch progress under the **Logs** tab. This takes a few minutes the first time (it's installing PyTorch and downloading AI models).
- Once it says **Running**, click **App** at the top — that's your public URL, something like `https://huggingface.co/spaces/<your-username>/<your-space-name>`.
- If you set an `ACCESS_CODE`, you (and anyone you share the link with) will see a small login screen first.

### Good to know about the free tier
- **Storage resets on restart.** Free Spaces don't have permanent disk storage — if the Space sleeps (after ~48 hours of no visits) and wakes back up, or if you push a new update, previously uploaded PDFs and their vector caches are gone and need to be re-uploaded. This is fine for a demo/portfolio project; it's not a place to permanently store documents.
- **Cold starts.** The first request after the Space has been asleep can take 15–30 seconds while it wakes up.
- **Updating your app later:** just push new commits to the `space` remote (`git push space main`) and it rebuilds automatically.

### Alternative: Render.com
[Render](https://render.com) also has a free web-service tier and deploys straight from your GitHub repo with no extra git remote needed — but its free tier only gives **512 MB RAM**, which is tight for this app's embedding models. If you go this route, make sure to set the lighter `DEFAULT_EMBEDDING_MODEL` and `RERANK_MODEL` values from Step 4 above (as Environment Variables in Render's dashboard, plus `GEMINI_API_KEY` and `ACCESS_CODE` as Secret values), and expect the free instance to spin down after 15 minutes of inactivity with a slower cold start on the next visit.

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
