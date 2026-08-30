"""
agentic_rag.py
===============
Step 10: extend the plain RAG pipeline (rag_system.py) into a very small
"agentic" workflow.

A plain RAG pipeline always does: retrieve once -> generate once.
An agentic RAG pipeline lets the model act more like a researcher:

    1. ROUTE   - decide whether the question even needs the course
                 catalogue, or is just small talk / out of scope.
    2. RETRIEVE - pull the top-k chunks (same retriever as rag_system.py).
    3. GRADE    - ask the model to judge whether the retrieved chunks are
                  actually sufficient to answer the question.
    4. REFINE   - if not sufficient, rewrite the query (e.g. add synonyms,
                  split a multi-part question) and retrieve again, up to
                  a small retry budget.
    5. ANSWER   - generate the final, grounded answer with sources.

This is intentionally simple (no external agent framework) so the control
flow is easy to read: it's just a Python loop calling the same building
blocks from rag_system.py (retrieve, build_prompt, ask_groq) plus one
extra "self-check" LLM call.
"""

from typing import Dict, List, Tuple

from rag_system import (
    Document,
    VectorStore,
    ask_groq,
    build_prompt,
    build_store,
)

MAX_RETRIES = 2


def route(question: str) -> bool:
    """
    Step 1 - ROUTE.
    Cheap, local heuristic instead of burning an LLM call: if the question
    contains catalogue-ish vocabulary, send it to retrieval. Otherwise,
    treat it as out of scope. (You could swap this for an LLM call too;
    it's written as a plain function so it's easy to replace.)
    """
    catalogue_keywords = [
        "course", "credit", "prerequisite", "pre-requisite", "elective",
        "core", "capstone", "jagsom", "pgdm", "syllabus", "competenc",
        "module", "program", "finance", "marketing", "hr", "analytics",
        "banking", "internship",
    ]
    q = question.lower()
    return any(k in q for k in catalogue_keywords)


def grade_context(question: str, retrieved: List[Tuple[Document, float]]) -> bool:
    """
    Step 3 - GRADE.
    Ask the LLM a cheap yes/no question: "can this context answer the
    question?" This is the classic 'self-RAG' / 'corrective RAG' idea,
    kept to a single constrained call.
    """
    if not retrieved:
        return False

    context_text = "\n\n".join(doc.text for doc, _ in retrieved)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a strict grader. Given a QUESTION and CONTEXT, reply with "
                "exactly one word: YES if the context contains enough information "
                "to answer the question, or NO if it does not."
            ),
        },
        {"role": "user", "content": f"QUESTION: {question}\n\nCONTEXT:\n{context_text}"},
    ]
    # The budget has to cover the model's hidden reasoning as well as the one
    # word we want back; too small a budget truncates mid-thought and every
    # grade silently comes back NO, which pushes the agent into needless retries.
    try:
        verdict = ask_groq(messages, temperature=0.0, max_tokens=700).strip().upper()
    except Exception:
        return True  # grading is an optimisation; never fail the whole answer on it
    if not verdict:
        return True  # reply was truncated: fail open rather than burn a retry
    return verdict.startswith("Y") or "YES" in verdict[:40]


def refine_query(question: str, attempt: int) -> str:
    """
    Step 4 - REFINE.
    Asks the LLM to rewrite the query for better retrieval (e.g. expand
    abbreviations, add likely course-catalogue vocabulary). Falls back to
    the original question if the rewrite call fails for any reason.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "Rewrite the user's question into a short, keyword-rich search "
                "query optimized for retrieving matching sections from a business "
                "school course catalogue. Return ONLY the rewritten query, no "
                "explanation."
            ),
        },
        {"role": "user", "content": question},
    ]
    try:
        # The budget must leave room for the model's hidden reasoning; too tight
        # and the rewrite comes back empty, which would search for nothing at all.
        rewritten = ask_groq(messages, temperature=0.3, max_tokens=400).strip()
    except Exception:
        return question
    # Never let an empty or degenerate rewrite replace a usable question.
    return rewritten if len(rewritten) >= 3 else question


def agentic_answer(store: VectorStore, question: str, top_k: int = 4) -> Dict:
    """
    Full agentic loop tying steps 1-5 together.
    Returns a dict with the final answer, the sources used, and a trace of
    what the agent did (useful for the 'show your work' part of the demo).
    """
    trace: List[str] = []

    if not route(question):
        trace.append("ROUTE: question judged out of scope for the catalogue.")
        return {
            "question": question,
            "answer": (
                "This doesn't look like a question about the JAGSoM PGDM course "
                "catalogue, so I won't search it. Ask me about specific courses, "
                "credits, pre-requisites, or electives instead."
            ),
            "sources": [],
            "trace": trace,
        }

    trace.append("ROUTE: question is in scope, proceeding to retrieval.")

    current_query = question
    retrieved: List[Tuple[Document, float]] = []
    # Keep the strongest retrieval seen so far: a rewritten query can easily
    # score worse than the original, and we must never answer from a weaker
    # (or empty) context just because it came last.
    best: List[Tuple[Document, float]] = []
    best_score = -1.0

    def top_score(hits: List[Tuple[Document, float]]) -> float:
        return hits[0][1] if hits else 0.0

    for attempt in range(MAX_RETRIES + 1):
        retrieved = store.retrieve(current_query, top_k=top_k)
        trace.append(
            f"RETRIEVE (attempt {attempt + 1}): query='{current_query}' -> "
            f"{len(retrieved)} chunks."
        )

        if top_score(retrieved) > best_score:
            best, best_score = retrieved, top_score(retrieved)

        sufficient = grade_context(question, best)
        trace.append(f"GRADE (attempt {attempt + 1}): sufficient={sufficient}")

        if sufficient or attempt == MAX_RETRIES:
            break

        refined = refine_query(question, attempt)
        if refined == current_query:
            trace.append("REFINE: rewrite matched the previous query, stopping early.")
            break
        current_query = refined
        trace.append(f"REFINE: rewrote query to '{current_query}'")

    retrieved = best
    messages = build_prompt(question, retrieved)
    answer = ask_groq(messages) or (
        "I found related pages in the catalogue but couldn't summarise them. "
        "Try asking about a specific course, credit count, or pre-requisite."
    )
    trace.append("ANSWER: generated final grounded response.")

    sources = [
        {
            "rank": i + 1,
            "title": doc.metadata.get("title"),
            "page": doc.metadata.get("page"),
            "similarity": round(score, 3),
        }
        for i, (doc, score) in enumerate(retrieved)
    ]

    return {"question": question, "answer": answer, "sources": sources, "trace": trace}


def print_agentic_result(result: Dict) -> None:
    print(f"\nQ: {result['question']}")
    print("\nAgent trace:")
    for step in result["trace"]:
        print(f"  - {step}")
    print(f"\nA: {result['answer']}")
    if result["sources"]:
        print("\nSources used:")
        for s in result["sources"]:
            print(f"  [{s['rank']}] {s['title']} (page {s['page']}, similarity={s['similarity']})")


if __name__ == "__main__":
    store = build_store()

    demo_questions = [
        "How's the weather today?",  # out of scope -> ROUTE should stop it
        "I want a job in credit risk, what courses build that path?",  # needs refinement/synthesis
        "What's the credit count for MSME Financing?",
    ]

    for q in demo_questions:
        result = agentic_answer(store, q)
        print_agentic_result(result)
        print("-" * 80)
