"""
rag_system.py
==============
A minimal, dependency-light Retrieval-Augmented Generation (RAG) system
built on top of the JAGSoM PGDM 2025-27 Course Catalogue.

Covers steps 1-9 of the assignment:
    1. Build a small knowledge base        -> load_knowledge_base()
    2. Split documents into chunks          -> chunk_pages()
    3. Convert chunks into embeddings       -> VectorStore.build()
    4. Convert a question into an embedding -> VectorStore._embed_query()
    5. Retrieve the most relevant chunks    -> VectorStore.retrieve()
    6. Place chunks inside a prompt         -> build_prompt()
    7. Ask a Groq model, answer-only-from-context -> ask_groq()
    8. Show the sources used                -> answer_question()
    9. Compare RAG vs. ordinary generation  -> compare_rag_vs_plain()

No LangChain / LlamaIndex / FAISS / Chroma / MCP / external vector DB is used.
Embeddings are computed locally with scikit-learn's TF-IDF vectorizer +
cosine similarity — this is a legitimate, if simple, embedding + retrieval
scheme and needs no network call and no paid embedding API.

The only network call this script makes is the final generation step,
which talks to the Groq Chat Completions REST API.

------------------------------------------------------------------------
SECURITY NOTE (read this before running):
You pasted a live Groq API key in plain text in our chat. Treat that key
as compromised — revoke/regenerate it at https://console.groq.com/keys
and never paste real keys into a chat window. This script deliberately
does NOT contain any key. It reads GROQ_API_KEY from your environment
(or a local .env file that you keep out of version control).
------------------------------------------------------------------------
"""

import io
import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

import pdfplumber
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    import requests
except ImportError as e:
    raise SystemExit("Please `pip install requests` first.") from e

try:
    from dotenv import load_dotenv  # optional convenience: reads a local .env file
    load_dotenv()
except ImportError:
    pass  # fine if python-dotenv isn't installed; env vars can be set another way


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))

# Default to the catalogue that sits next to this file, so the script works
# no matter which directory you launch it from.
PDF_PATH = os.environ.get("KB_PDF_PATH", os.path.join(_HERE, "catalogue.pdf"))
CHUNKS_JSON_PATH = os.environ.get("KB_CHUNKS_PATH", os.path.join(_HERE, "catalogue_chunks.json"))
GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.6-27b")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TIMEOUT = float(os.environ.get("GROQ_TIMEOUT", "60"))
TOP_K = 4  # how many chunks to retrieve per question


# --------------------------------------------------------------------------
# Step 1: Build a small knowledge base
# --------------------------------------------------------------------------
@dataclass
class Document:
    doc_id: str
    text: str
    metadata: Dict = field(default_factory=dict)


def load_knowledge_base(pdf_path: str = PDF_PATH) -> List[Document]:
    """
    Reads the PDF page by page. Each page of this catalogue corresponds
    almost 1:1 to a single course (or a section header/table page), which
    makes 'one page = one raw document' a natural starting unit before we
    chunk further in step 2.
    """
    docs: List[Document] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            raw = page.extract_text() or ""
            raw = raw.strip()
            if not raw:
                continue
            docs.append(Document(doc_id=f"page_{i:03d}", text=raw, metadata={"page": i}))
    return docs


def load_knowledge_base_from_bytes(
    file_bytes: bytes, filename: str = "custom_catalogue.pdf"
) -> List[Document]:
    """Reads PDF bytes in-memory for user uploads."""
    docs: List[Document] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            raw = page.extract_text() or ""
            raw = raw.strip()
            if not raw:
                continue
            docs.append(
                Document(
                    doc_id=f"page_{i:03d}",
                    text=raw,
                    metadata={"page": i, "filename": filename},
                )
            )
    return docs



# --------------------------------------------------------------------------
# Step 2: Split documents into chunks
# --------------------------------------------------------------------------
FOOTER_PATTERN = re.compile(r"JAGSOM/Course Catalogue/25-27/RK/28 Jul 2025")


def _clean(text: str) -> str:
    text = FOOTER_PATTERN.sub("", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _course_title(text: str) -> str:
    """Best-effort guess at the course name: first non-empty, non-numeric line."""
    for line in text.split("\n"):
        line = line.strip()
        if line and not line.isdigit() and len(line) < 90:
            return line
    return "Untitled section"


def chunk_pages(docs: List[Document], max_chars: int = 1600, overlap: int = 150) -> List[Document]:
    """
    Most pages in this catalogue are already a coherent unit (one course
    brief). We keep short/medium pages as single chunks so retrieval stays
    semantically clean ("give me the whole Corporate Finance brief"),
    and only split unusually long pages (e.g. the elective tables) into
    overlapping windows so no chunk is too big for the prompt.
    """
    chunks: List[Document] = []
    for doc in docs:
        text = _clean(doc.text)
        title = _course_title(text)

        if len(text) <= max_chars:
            chunks.append(
                Document(
                    doc_id=f"{doc.doc_id}_c0",
                    text=text,
                    metadata={**doc.metadata, "title": title},
                )
            )
            continue

        start = 0
        idx = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            piece = text[start:end]
            chunks.append(
                Document(
                    doc_id=f"{doc.doc_id}_c{idx}",
                    text=piece,
                    metadata={**doc.metadata, "title": title},
                )
            )
            idx += 1
            if end == len(text):
                break
            start = end - overlap
    return chunks


# --------------------------------------------------------------------------
# Steps 3-5: Embeddings + retrieval (a tiny in-memory vector store)
# --------------------------------------------------------------------------
class VectorStore:
    """
    A from-scratch, in-memory 'vector database' — no FAISS/Chroma needed.

    Embeddings here are TF-IDF vectors (bag-of-words weighted by term
    importance). This is a genuine embedding technique: each chunk and
    each query is mapped to a fixed-length numeric vector in the same
    space, and similarity between vectors approximates semantic overlap.
    It runs entirely offline, which keeps the demo self-contained and
    keeps the Groq API reserved for what it's actually needed for:
    generation, not embedding.
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            stop_words="english", max_df=0.85, ngram_range=(1, 2), sublinear_tf=True
        )
        self.chunks: List[Document] = []
        self.matrix = None  # shape: (n_chunks, n_terms)

    def build(self, chunks: List[Document]) -> None:
        """Step 3: convert every chunk into an embedding vector."""
        self.chunks = chunks
        corpus = [c.text for c in chunks]
        self.matrix = self.vectorizer.fit_transform(corpus)

    def _embed_query(self, question: str):
        """Step 4: convert the incoming question into an embedding vector,
        using the SAME vector space the chunks were embedded into."""
        return self.vectorizer.transform([question])

    def retrieve(self, question: str, top_k: int = TOP_K) -> List[Tuple[Document, float]]:
        """Step 5: rank chunks by cosine similarity to the query vector."""
        q_vec = self._embed_query(question)
        sims = cosine_similarity(q_vec, self.matrix).flatten()
        ranked_idx = np.argsort(-sims)[:top_k]
        return [(self.chunks[i], float(sims[i])) for i in ranked_idx if sims[i] > 0]


# --------------------------------------------------------------------------
# Step 6: Place the retrieved chunks inside a prompt
# --------------------------------------------------------------------------
def build_prompt(question: str, retrieved: List[Tuple[Document, float]]) -> List[Dict]:
    context_blocks = []
    for i, (doc, score) in enumerate(retrieved, start=1):
        label = doc.metadata.get("title", doc.doc_id)
        context_blocks.append(f"[Source {i} | {label} | page {doc.metadata.get('page')}]\n{doc.text}")
    context_text = "\n\n".join(context_blocks) if context_blocks else "(no relevant context found)"

    system_prompt = (
        "You are a helpful assistant answering questions about the JAGSoM PGDM "
        "2025-27 Course Catalogue. Answer ONLY using the CONTEXT provided below. "
        "If the answer is not contained in the context, say clearly that the "
        "catalogue does not cover that, instead of guessing. When you use a fact, "
        "mention which Source number it came from."
    )
    user_prompt = f"CONTEXT:\n{context_text}\n\nQUESTION: {question}"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


# --------------------------------------------------------------------------
# Step 7: Ask the Groq model, grounded strictly in retrieved chunks
# --------------------------------------------------------------------------
def _get_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Export it in your shell "
            "(export GROQ_API_KEY=...) or put it in a local .env file "
            "that is excluded from git. Never hard-code it in source."
        )
    return key


# Reasoning models on Groq (e.g. the qwen3 family) wrap their scratchpad in
# <think>...</think> before the real answer. That scratchpad is not the answer
# and must never reach the UI, so we strip it centrally here.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"^\s*<think>.*", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Remove <think> scratchpad blocks from a model reply."""
    cleaned = _THINK_BLOCK.sub("", text)
    # An unterminated block means the reply was cut off mid-thought (max_tokens
    # too small). Nothing usable follows, so drop it rather than show raw notes.
    cleaned = _THINK_OPEN.sub("", cleaned)
    return cleaned.strip()


def ask_groq(messages: List[Dict], temperature: float = 0.2, max_tokens: int = 2000) -> str:
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=GROQ_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    message = data["choices"][0]["message"]
    # Some Groq models return the scratchpad in a separate field; either way we
    # only ever want message.content, with any inline <think> block removed.
    return strip_reasoning(message.get("content") or "")


# --------------------------------------------------------------------------
# Step 8: Answer a question end-to-end and show sources
# --------------------------------------------------------------------------
def answer_question(store: VectorStore, question: str, top_k: int = TOP_K) -> Dict:
    retrieved = store.retrieve(question, top_k=top_k)
    messages = build_prompt(question, retrieved)
    answer = ask_groq(messages) or (
        "I couldn't produce an answer for that. Try rephrasing the question with "
        "the course name or topic you're interested in."
    )

    sources = [
        {
            "rank": i + 1,
            "title": doc.metadata.get("title"),
            "page": doc.metadata.get("page"),
            "similarity": round(score, 3),
        }
        for i, (doc, score) in enumerate(retrieved)
    ]

    return {"question": question, "answer": answer, "sources": sources}


# --------------------------------------------------------------------------
# Step 9: Compare RAG vs. ordinary (ungrounded) generation
# --------------------------------------------------------------------------
def compare_rag_vs_plain(store: VectorStore, question: str) -> Dict:
    rag_result = answer_question(store, question)

    plain_messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Answer the question directly from your own knowledge.",
        },
        {"role": "user", "content": question},
    ]
    plain_answer = ask_groq(plain_messages)

    return {
        "question": question,
        "rag_answer": rag_result["answer"],
        "rag_sources": rag_result["sources"],
        "plain_answer": plain_answer,
    }


# --------------------------------------------------------------------------
# Pretty printers (used by main / notebook demo)
# --------------------------------------------------------------------------
def print_answer(result: Dict) -> None:
    print(f"\nQ: {result['question']}")
    print(f"\nA: {result['answer']}")
    print("\nSources used:")
    for s in result["sources"]:
        print(f"  [{s['rank']}] {s['title']} (page {s['page']}, similarity={s['similarity']})")


def print_comparison(result: Dict) -> None:
    print(f"\nQ: {result['question']}")
    print("\n--- RAG answer (grounded in the catalogue) ---")
    print(result["rag_answer"])
    print("\nSources used:")
    for s in result["rag_sources"]:
        print(f"  [{s['rank']}] {s['title']} (page {s['page']}, similarity={s['similarity']})")
    print("\n--- Plain LLM answer (no retrieval) ---")
    print(result["plain_answer"])


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def build_store(pdf_path: str = PDF_PATH) -> VectorStore:
    # 1. Ultra-fast path: load pre-extracted JSON chunks if present
    if os.path.exists(CHUNKS_JSON_PATH):
        try:
            with open(CHUNKS_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            chunks = [
                Document(doc_id=d["doc_id"], text=d["text"], metadata=d.get("metadata", {}))
                for d in data
            ]
            store = VectorStore()
            store.build(chunks)
            print(f"Knowledge base loaded from JSON: {len(chunks)} chunks.")
            return store
        except Exception as e:
            print(f"Warning: Failed to load from JSON ({e}), falling back to PDF.")

    # 2. Standard path: parse PDF
    docs = load_knowledge_base(pdf_path)
    chunks = chunk_pages(docs)
    store = VectorStore()
    store.build(chunks)
    print(f"Knowledge base ready: {len(docs)} pages -> {len(chunks)} chunks.")
    return store


def build_store_from_docs(docs: List[Document]) -> VectorStore:
    """Builds an in-memory TF-IDF VectorStore directly from a list of Document objects."""
    chunks = chunk_pages(docs)
    store = VectorStore()
    store.build(chunks)
    print(f"Knowledge base built from uploaded docs: {len(docs)} pages -> {len(chunks)} chunks.")
    return store


if __name__ == "__main__":
    store = build_store()

    demo_questions = [
        "What are the pre-requisites for the Corporate Finance course?",
        "Which elective should I take if I'm interested in NLP and unstructured data?",
        "What is the credit value of the Industry Internship Program?",
    ]

    for q in demo_questions:
        result = answer_question(store, q)
        print_answer(result)
        print("-" * 80)
