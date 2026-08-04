# PubMedAgent 🧬🧠

PubMedAgent is an advanced, full-stack, autonomous AI agent designed for biomedical literature retrieval and synthesis. It empowers clinicians and researchers to search, retrieve, evaluate, and dynamically build a vector knowledge base of medical literature using natural language.

By orchestrating multiple specialized LLM sub-agents (via LangGraph) and utilizing high-performance vector databases (Qdrant), PubMedAgent translates complex clinical questions into structured search queries, retrieves the most relevant Open Access evidence, checks for full-text PDF availability, and performs on-demand ingestion of full-text papers into its hybrid retrieval engine.

---

## ✨ Key Features

### 🔍 Agentic Search Pipeline (LangGraph)
- **Natural Language to Boolean**: Converts complex clinical cases into highly specific PubMed Boolean queries.
- **Reranker & Grader**: Synthesizes abstract content and rigorously scores papers based on Semantic Similarity, Recency, Citation Count, and Journal Quality (SJR index).
- **Q&A Agent**: Answers user questions directly using the retrieved context, citing specific papers as evidence.

### 📄 On-Demand Full-Text Ingestion & PDF Proxy
- **Multi-Provider Availability Checking**: Falls back across 4 major APIs (Europe PMC, NCBI PMC, Unpaywall, Crossref) to locate free Open Access PDFs.
- **Proxy Downloading**: Downloads PDFs securely through the backend without exposing the frontend to CORS limitations or publisher firewalls.
- **Vector Database Augmentation**: Automatically extracts text from PDFs (using `PyMuPDF`), chunks it semantically (via `langchain`), generates embeddings, and pushes it to a global `Qdrant` collection.
- **Hybrid LLM Retrieval**: Once a paper is indexed, future clinical queries pull deep context from *both* the PubMed abstracts and the global full-text database.

### ⚡ Responsive Frontend
- **Real-Time Streaming**: Uses Server-Sent Events (SSE) to live-stream backend processing progress (e.g., `Downloading PDF...` -> `Extracting text...` -> `Chunking...`).
- **Modern UI**: Built with Next.js, TailwindCSS, Zustand for state management, and `react-markdown` for rendering scientific text and citations.
- **Multi-Threading UI**: Run full-text indexing jobs simultaneously across multiple papers with live progress bars.

---

## 🛠️ Technology Stack

- **Backend**: Python, FastAPI, LangChain, LangGraph, PyMuPDF (fitz), httpx.
- **Database / Vector Store**: SQLite (Conversation histories & Auth), Qdrant (Abstract & Full-Text Embeddings).
- **LLM Provider**: Groq API (Defaulting to `qwen/qwen3.6-27b`).
- **Frontend**: Next.js (React 18), Tailwind CSS, TypeScript, Zustand.

---

## 🚀 How to Run from Scratch

Follow these steps to deploy both the backend and frontend locally.

### 1. Prerequisites
- **Python 3.11+** installed on your machine.
- **Node.js 18+** and `npm` installed.
- A **Groq API Key** (Free tier available at [groq.com](https://groq.com)).

### 2. Backend Setup

1. **Navigate to the root directory**:
   ```bash
   cd PubmedAgent
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: Ensure you have `PyMuPDF`, `langchain`, `qdrant-client`, `fastapi`, and `uvicorn` installed.)*

4. **Set up Environment Variables**:
   Create a `.env` file in the root directory (if it doesn't exist) and add your Groq API key:
   ```env
   GROQ_API_KEY="your_groq_api_key_here"
   GROQ_MODEL="qwen/qwen3.6-27b"
   TOKENIZERS_PARALLELISM="false"
   ```

5. **Start the FastAPI Backend**:
   ```bash
   uvicorn app:app --reload --port 8000
   ```
   The backend will now be running at `http://localhost:8000`.

### 3. Frontend Setup

1. **Open a new terminal window** and navigate to the frontend directory:
   ```bash
   cd PubmedAgent/Frontend
   ```

2. **Install Node dependencies**:
   ```bash
   npm install
   ```

3. **Set up Frontend Environment Variables**:
   Create a `.env.local` file inside the `Frontend` directory to point to your backend:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

4. **Start the Next.js Development Server**:
   ```bash
   npm run dev
   ```

### 4. Using the App
- Open your browser and navigate to `http://localhost:3000`.
- Create a new account or log in.
- Start a new conversation and input a clinical scenario (e.g., *"What is the evidence for omitting lymph nodes in prostate cancer radiotherapy for a patient with Gleason score 8?"*).
- Click **Check Full Text Availability** to locate PDFs.
- Click **Add to DB** to ingest the PDF directly into the Qdrant Vector database for future deep-retrieval QA!

---

## ⚙️ Architecture Notes
- **Authentication**: JWT-based auth is implemented and stored via SQLite (`conversations.db`).
- **Qdrant Vector Database**: By default, Qdrant runs entirely in memory (`:memory:` fallback) or via a local persistent file depending on your `src/config.py`. It manages two distinct spaces: conversational metadata (isolated per chat) and `pubmed_fulltext` (global knowledge).
- **Publisher Firewalls**: The PDF downloader proxy is configured to mimic standard browser `User-Agent` strings to seamlessly bypass basic 403 Forbidden publisher firewalls.
