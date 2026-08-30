"""
api/index.py
============
Vercel Serverless Function & Local Flask Entrypoint for KYC — Know Your Courses.
Exposes agentic RAG endpoints over JSON and handles PDF catalogue uploads.
"""

import os
import sys
import uuid
# api.py is at root, so we can import directly
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from agentic_rag import agentic_answer
from rag_system import (
    build_store,
    load_knowledge_base_from_bytes,
    build_store_from_docs,
)
_HERE = os.path.dirname(os.path.abspath(__file__))
GUI_DIST = os.path.join(_HERE, "gui", "dist")

app = Flask(
    __name__,
    static_folder=GUI_DIST if os.path.exists(GUI_DIST) else None,
    static_url_path="",
)
CORS(app)

PORT = int(os.environ.get("PORT", "5350"))

_default_store = None
_custom_stores = {}


def get_store(session_id: str = None):
    global _default_store
    if session_id and session_id in _custom_stores:
        return _custom_stores[session_id]["store"]
    if _default_store is None:
        print("Initializing default knowledge base...")
        _default_store = build_store()
        print("Initialization complete.")
    return _default_store


@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def health():
    """Lets the GUI show a live connection badge."""
    try:
        session_id = request.args.get("session_id")
        store = get_store(session_id)
        catalogue_name = (
            _custom_stores[session_id]["filename"]
            if session_id and session_id in _custom_stores
            else "JAGSoM PGDM 2025-27"
        )
        return jsonify(
            {
                "status": "ok",
                "chunks": len(store.chunks),
                "catalogue": catalogue_name,
            }
        )
    except Exception as e:
        print(f"Health check error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/upload", methods=["POST"])
@app.route("/api/upload", methods=["POST"])
def upload():
    """Accepts a custom Course Catalogue PDF upload and builds an in-memory RAG index."""
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded. Expected form field 'file'."}), 400

    filename = file.filename or "uploaded_catalogue.pdf"
    if not filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are currently supported."}), 400

    try:
        file_bytes = file.read()
        if not file_bytes:
            return jsonify({"error": "Uploaded file is empty."}), 400

        docs = load_knowledge_base_from_bytes(file_bytes, filename=filename)
        if not docs:
            return jsonify({"error": "No readable text could be extracted from this PDF."}), 400

        custom_store = build_store_from_docs(docs)
        session_id = str(uuid.uuid4())
        _custom_stores[session_id] = {
            "store": custom_store,
            "filename": filename,
            "pages": len(docs),
            "chunks": len(custom_store.chunks),
        }

        print(f"Successfully processed {filename}: {len(docs)} pages, {len(custom_store.chunks)} chunks (Session: {session_id})")

        return jsonify(
            {
                "status": "ok",
                "session_id": session_id,
                "filename": filename,
                "pages": len(docs),
                "chunks": len(custom_store.chunks),
                "message": f"Successfully indexed {filename}",
            }
        )
    except Exception as e:
        print(f"Error processing catalogue upload: {e}")
        return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500


@app.route("/chat", methods=["POST"])
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data or not str(data.get("message", "")).strip():
        return jsonify({"error": "Missing 'message' field in JSON body"}), 400

    question = str(data["message"]).strip()
    session_id = data.get("session_id")
    print(f"Received question: {question} (session: {session_id})")

    try:
        store = get_store(session_id)
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
                "health": "GET /api/health",
                "upload": "POST /api/upload",
                "chat": "POST /api/chat",
            },
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True, use_reloader=False)
