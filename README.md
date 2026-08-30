# KYC — Know Your Courses

An agentic RAG assistant over the JAGSoM PGDM 2025-27 Course Catalogue, with a
3D education-themed web UI.

A from-scratch Retrieval-Augmented Generation (RAG) demo built directly on
`catalogue.pdf` — no LangChain, LlamaIndex, FAISS, Chroma, MCP server, or
external vector database. Just `pdfplumber` + `scikit-learn` (TF-IDF) +
`requests` (to call the Groq API).

## ⚠️ Before you do anything else: rotate your API key

The key you pasted in chat (`gsk_yVWl...`) is now exposed and should be
treated as compromised. Go to **https://console.groq.com/keys**, revoke it,
generate a new one, and never paste a real key into a chat prompt again.
This project never hard-codes a key — it reads `GROQ_API_KEY` from your
environment or a local `.env` file that you keep out of git.

## Setup

```bash
cd rag_project
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and paste your NEW (rotated) key into GROQ_API_KEY=
```

Make sure `catalogue.pdf` sits in this folder (or set `KB_PDF_PATH` in `.env`
to point elsewhere).

## Run it

```bash
python3 rag_system.py      # steps 1-9: build KB, retrieve, answer, show sources
python3 agentic_rag.py     # step 10: agentic RAG (route -> retrieve -> grade -> refine -> answer)
```

## Run the KYC web app

Two processes: the Flask API (agentic pipeline) and the Vite/React GUI.

```bash
python3 api.py
```

```bash
npm --prefix gui install && npm --prefix gui run dev
```

- API: <http://localhost:5350> (`GET /health`, `POST /chat {"message": "..."}`)
- GUI: <http://localhost:5300>

Set `VITE_API_BASE` in `gui/.env` if the API runs anywhere other than
`http://localhost:5350`.

## How each step maps to the code

| # | Step | Where |
|---|------|-------|
| 1 | Build a small knowledge base | `load_knowledge_base()` — reads `catalogue.pdf` page by page with `pdfplumber` |
| 2 | Split documents into chunks | `chunk_pages()` — each course brief is naturally ~1 page; long pages get windowed with overlap |
| 3 | Convert chunks into embeddings | `VectorStore.build()` — TF-IDF vectors via scikit-learn (no external embedding API) |
| 4 | Convert a question into an embedding | `VectorStore._embed_query()` — same TF-IDF space as the chunks |
| 5 | Retrieve the most relevant chunks | `VectorStore.retrieve()` — cosine similarity, top-k |
| 6 | Place chunks inside a prompt | `build_prompt()` — numbered `[Source N]` blocks + instructions to answer only from context |
| 7 | Ask a Groq model, grounded only in context | `ask_groq()` — calls `qwen/qwen3.6-27b` (override with `GROQ_MODEL`) via the Groq Chat Completions REST API, stripping the model's `<think>` scratchpad |
| 8 | Show the sources used | `answer_question()` / `print_answer()` — returns page number + similarity score per source |
| 9 | Compare RAG vs. ordinary generation | `compare_rag_vs_plain()` — runs the same question with and without retrieval, side by side |
| 10 | Agentic RAG | `agentic_rag.py` — adds routing, a "does this context suffice?" grading call, and up to 2 query-rewrite retries before answering |

## Why TF-IDF instead of a "real" embedding model?

Groq's API is a chat-completions API — it doesn't serve embeddings. Rather
than reach for a separate paid embedding API (OpenAI, Cohere, etc.) or pull
in FAISS/Chroma, this demo uses `TfidfVectorizer` + cosine similarity as a
lightweight, fully local, zero-dependency-on-the-network embedding +
retrieval layer. It's not as strong as a neural embedding model on
paraphrased queries, but for a keyword-rich domain like a course catalogue
(course names, "pre-requisites", "credits") it performs well and keeps the
whole retrieval stack inspectable in about 40 lines of code.

If you want to swap in real embeddings later, the only place you'd touch is
`VectorStore` — the rest of the pipeline (chunking, prompting, generation,
agentic loop) doesn't care how the vectors were made.

## Example queries to try

- "What are the pre-requisites for Corporate Finance?"
- "Which electives are relevant if I want to work in credit risk?"
- "How many credits is the Industry Internship Program worth?"
- "I'm interested in NLP — which Business Analytics electives should I take?"
- (agentic demo) "How's the weather today?" → should be routed out of scope
