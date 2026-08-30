"""
api.py
======
HTTP layer for KYC — Know Your Courses.

Serves the React GUI in gui/ and exposes the agentic RAG pipeline over JSON.
"""

import os

from flask import Flask, jsonify, request
from flask_cors import CORS

from agentic_rag import agentic_answer
from rag_system import build_store

app = Flask(__name__)
CORS(app)  # the Vite dev server runs on a different origin

PORT = int(os.environ.get("PORT", "5350"))

print("Initializing knowledge base...")
store = build_store()
print("Initialization complete.")


@app.route("/", methods=["GET"])
def root():
    """Provides status information and links to the frontend GUI."""
    return jsonify(
        {
            "name": "KYC — Know Your Courses API",
            "status": "running",
            "frontend_gui": "http://localhost:5300",
            "endpoints": {
                "health": "GET /health",
                "chat": "POST /chat",
            },
        }
    )


@app.route("/health", methods=["GET"])
def health():
    """Lets the GUI show a live connection badge instead of failing blind."""
    return jsonify({"status": "ok", "chunks": len(store.chunks)})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data or not str(data.get("message", "")).strip():
        return jsonify({"error": "Missing 'message' field in JSON body"}), 400

    question = str(data["message"]).strip()
    print(f"Received question: {question}")

    try:
        result = agentic_answer(store, question)
        return jsonify(
            {
                "answer": result["answer"],
                "sources": result["sources"],
                "trace": result.get("trace", []),
            }
        )
    except Exception as e:
        print(f"Error answering question: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True, use_reloader=False)
