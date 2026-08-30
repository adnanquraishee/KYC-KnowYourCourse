"""
api.py
======
HTTP layer for KYC — Know Your Courses.
Exposes the agentic RAG pipeline over JSON endpoints and serves the React GUI.
"""

import os
import sys

# Ensure repository root is on sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from agentic_rag import agentic_answer
from rag_system import build_store

GUI_DIST = os.path.join(_HERE, "gui", "dist")

app = Flask(
    __name__,
    static_folder=GUI_DIST if os.path.exists(GUI_DIST) else None,
    static_url_path="",
)
CORS(app)

PORT = int(os.environ.get("PORT", "5350"))

_store = None


def get_store():
    global _store
    if _store is None:
        print("Initializing knowledge base...")
        _store = build_store()
        print("Initialization complete.")
    return _store


@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
@app.route("/api/index/health", methods=["GET"])
@app.route("/api/index.py/health", methods=["GET"])
def health():
    """Lets the GUI show a live connection badge instead of failing blind."""
    store = get_store()
    return jsonify({"status": "ok", "chunks": len(store.chunks)})


@app.route("/chat", methods=["POST"])
@app.route("/api/chat", methods=["POST"])
@app.route("/api/index/chat", methods=["POST"])
@app.route("/api/index.py/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data or not str(data.get("message", "")).strip():
        return jsonify({"error": "Missing 'message' field in JSON body"}), 400

    question = str(data["message"]).strip()
    print(f"Received question: {question}")

    try:
        store = get_store()
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


@app.route("/", methods=["GET"])
@app.route("/<path:path>", methods=["GET"])
def serve_gui(path=""):
    """Serves the React GUI if built, or returns API status info if not built."""
    if path and os.path.exists(os.path.join(GUI_DIST, path)):
        return send_from_directory(GUI_DIST, path)
    if os.path.exists(os.path.join(GUI_DIST, "index.html")):
        return send_from_directory(GUI_DIST, "index.html")
    return jsonify(
        {
            "name": "KYC — Know Your Courses API",
            "status": "running",
            "message": "Frontend build not found. Run 'npm run build' inside gui/ to build the React UI.",
            "endpoints": {
                "health": "GET /health",
                "chat": "POST /chat",
            },
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True, use_reloader=False)
