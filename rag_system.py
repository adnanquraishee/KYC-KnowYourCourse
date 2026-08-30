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
Embeddings and retrieval are computed using a lightweight, pure-Python TF-IDF vectorizer +
cosine similarity — zero heavy external C-libraries (eliminating AWS Lambda/Vercel size limit crashes).

The only network call this script makes is the final generation step,
which talks to the Groq Chat Completions REST API.
"""

import io
import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

try:
    import requests
except ImportError as e:
    raise SystemExit("Please `pip install requests` first.") from e

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))

PDF_PATH = os.environ.get("KB_PDF_PATH", os.path.join(_HERE, "catalogue.pdf"))
CHUNKS_JSON_PATH = os.environ.get("KB_CHUNKS_PATH", os.path.join(_HERE, "catalogue_chunks.json"))
GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.6-27b")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TIMEOUT = float(os.environ.get("GROQ_TIMEOUT", "60"))
TOP_K = 4  # how many chunks to retrieve per question

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "could", "did",
    "do", "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "itself", "just", "me", "more", "most", "my", "myself", "no", "nor", "not",
    "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over",
    "own", "same", "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves"
}


# --------------------------------------------------------------------------
# Step 1: Build a small knowledge base
# --------------------------------------------------------------------------
@dataclass
class Document:
    doc_id: str
    text: str
    metadata: Dict = field(default_factory=dict)


def _extract_pdf_pages(stream_or_path, filename: str = "catalogue.pdf") -> List[Document]:
    docs: List[Document] = []
    # 1. Try pypdf (pure Python, fast, lightweight)
    try:
        import pypdf
        reader = pypdf.PdfReader(stream_or_path)
        for i, page in enumerate(reader.pages, start=1):
            raw = (page.extract_text() or "").strip()
            if raw:
                docs.append(Document(doc_id=f"page_{i:03d}", text=raw, metadata={"page": i, "filename": filename}))
        if docs:
            return docs
    except Exception:
        pass

    # 2. Fallback to pdfplumber if installed
    try:
        import pdfplumber
        with pdfplumber.open(stream_or_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                raw = (page.extract_text() or "").strip()
                if raw:
                    docs.append(Document(doc_id=f"page_{i:03d}", text=raw, metadata={"page": i, "filename": filename}))
    except Exception:
        pass

    return docs


def load_knowledge_base(pdf_path: str = PDF_PATH) -> List[Document]:
    """Reads the PDF page by page."""
    return _extract_pdf_pages(pdf_path, filename=os.path.basename(pdf_path))


def load_knowledge_base_from_bytes(
    file_bytes: bytes, filename: str = "custom_catalogue.pdf"
) -> List[Document]:
    """Reads PDF bytes in-memory for user uploads."""
    return _extract_pdf_pages(io.BytesIO(file_bytes), filename=filename)


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
    """Keeps short/medium course briefs as single chunks; windows long pages with overlap."""
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
        part = 0
        while start < len(text):
            end = start + max_chars
            segment = text[start:end].strip()
            if segment:
                chunks.append(
                    Document(
                        doc_id=f"{doc.doc_id}_c{part}",
                        text=segment,
                        metadata={**doc.metadata, "title": title, "part": part},
                    )
                )
                part += 1
            start += max_chars - overlap
    return chunks


# --------------------------------------------------------------------------
# Steps 3-5: Pure Python TF-IDF Vector Space & Cosine Similarity
# --------------------------------------------------------------------------
def _tokenize(text: str) -> List[str]:
    words = re.findall(r"\b[a-zA-Z0-9_\-\']+\b", text.lower())
    unigrams = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    bigrams = [
        f"{words[i]} {words[i+1]}"
        for i in range(len(words) - 1)
        if words[i] not in STOP_WORDS or words[i + 1] not in STOP_WORDS
    ]
    return unigrams + bigrams


class VectorStore:
    """
    A lightweight, pure-Python in-memory TF-IDF Vector Database.
    No scikit-learn or scipy C-extensions required — prevents Vercel/Lambda crashes.
    """

    def __init__(self):
        self.chunks: List[Document] = []
        self.idf: Dict[str, float] = {}
        self.doc_vectors: List[Dict[str, float]] = []
        self.doc_norms: List[float] = []

    def build(self, chunks: List[Document]) -> None:
        """Step 3: Convert every chunk into a TF-IDF embedding vector with title weighting."""
        self.chunks = chunks
        N = len(chunks)
        doc_tokens = []
        for c in chunks:
            text = c.text
            title = c.metadata.get("title", "")
            # Boost title relevance by including title terms with weight
            full_text = f"{title} {title} {text}" if title else text
            doc_tokens.append(_tokenize(full_text))

        df = Counter()
        for tokens in doc_tokens:
            df.update(set(tokens))

        max_doc_count = 0.85 * N
        self.idf = {
            term: math.log((1.0 + N) / (1.0 + freq)) + 1.0
            for term, freq in df.items()
            if freq <= max_doc_count
        }

        self.doc_vectors = []
        self.doc_norms = []
        for tokens in doc_tokens:
            counts = Counter(tokens)
            vec: Dict[str, float] = {}
            norm_sq = 0.0
            for term, count in counts.items():
                if term in self.idf:
                    weight = (1.0 + math.log(count)) * self.idf[term]
                    vec[term] = weight
                    norm_sq += weight * weight
            self.doc_vectors.append(vec)
            self.doc_norms.append(math.sqrt(norm_sq) if norm_sq > 0 else 1.0)

    def _embed_query(self, question: str) -> Tuple[Dict[str, float], float]:
        """Step 4: Convert question into TF-IDF vector in the same space."""
        q_tokens = _tokenize(question)
        q_counts = Counter(q_tokens)
        q_vec: Dict[str, float] = {}
        norm_sq = 0.0
        for term, count in q_counts.items():
            if term in self.idf:
                weight = (1.0 + math.log(count)) * self.idf[term]
                q_vec[term] = weight
                norm_sq += weight * weight
        return q_vec, math.sqrt(norm_sq) if norm_sq > 0 else 1.0

    def retrieve(self, question: str, top_k: int = TOP_K) -> List[Tuple[Document, float]]:
        """Step 5: Rank chunks by Cosine Similarity to the query vector."""
        q_vec, q_norm = self._embed_query(question)
        if not q_vec:
            return []

        scores: List[Tuple[Document, float]] = []
        for i, doc_vec in enumerate(self.doc_vectors):
            dot = sum(q_weight * doc_vec[term] for term, q_weight in q_vec.items() if term in doc_vec)
            if dot > 0:
                sim = dot / (q_norm * self.doc_norms[i])
                scores.append((self.chunks[i], float(sim)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# --------------------------------------------------------------------------
# Step 6: Place the retrieved chunks inside a prompt
# --------------------------------------------------------------------------
def build_prompt(question: str, retrieved: List[Tuple[Document, float]]) -> List[Dict]:
    context_blocks = []
    for i, (doc, score) in enumerate(retrieved, start=1):
        label = doc.metadata.get("title", doc.doc_id)
        page = doc.metadata.get("page", "?")
        context_blocks.append(f"[Source {i} | {label} | page {page}]\n{doc.text}")
    context_text = "\n\n".join(context_blocks) if context_blocks else "(no relevant context found)"

    system_prompt = (
        "You are a helpful assistant answering questions about the course catalogue. "
        "Answer ONLY using the CONTEXT provided below. "
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
            "GROQ_API_KEY is not set. Please add GROQ_API_KEY in your Vercel Environment Variables."
        )
    return key


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"^\s*<think>.*", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Remove <think> scratchpad blocks from a model reply."""
    cleaned = _THINK_BLOCK.sub("", text)
    cleaned = _THINK_OPEN.sub("", cleaned)
    return cleaned.strip()


def ask_groq(messages: List[Dict], temperature: float = 0.2, max_tokens: int = 2000) -> str:
    key = _get_api_key()
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=GROQ_TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text}")
    raw_content = resp.json()["choices"][0]["message"]["content"]
    return strip_reasoning(raw_content)


# --------------------------------------------------------------------------
# Step 8: Answer and return sources used
# --------------------------------------------------------------------------
def answer_question(store: VectorStore, question: str) -> Dict:
    retrieved = store.retrieve(question, top_k=TOP_K)
    messages = build_prompt(question, retrieved)
    answer = ask_groq(messages)

    sources = [
        {
            "rank": i,
            "title": doc.metadata.get("title", doc.doc_id),
            "page": doc.metadata.get("page"),
            "similarity": round(score, 3),
            "doc_id": doc.doc_id,
        }
        for i, (doc, score) in enumerate(retrieved, start=1)
    ]
    return {"question": question, "answer": answer, "sources": sources}


def print_answer(result: Dict) -> None:
    print(f"\nQ: {result['question']}")
    print(f"\nA: {result['answer']}")
    print("\nSources used:")
    for s in result["sources"]:
        print(f"  [{s['rank']}] {s['title']} (page {s['page']}, similarity={s['similarity']})")


def compare_rag_vs_plain(store: VectorStore, question: str) -> Dict:
    rag = answer_question(store, question)
    plain_messages = [
        {"role": "system", "content": "You are a helpful MBA admissions and curriculum assistant."},
        {"role": "user", "content": question},
    ]
    plain_answer = ask_groq(plain_messages)
    return {
        "question": question,
        "rag_answer": rag["answer"],
        "rag_sources": rag["sources"],
        "plain_answer": plain_answer,
    }


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
