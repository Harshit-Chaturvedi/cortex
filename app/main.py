"""
FastAPI app with /upload and /ask endpoints.
Run with: uvicorn app.main:app --reload
"""

import os
import time
import shutil
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import API_KEY, DOCS_DIR
from app.ingest import run_ingest
from app.qa_chain import ask

# basic logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cortex")


app = FastAPI(
    title="Cortex",
    description="RAG-based Q&A over your documents",
    version="0.1.0",
)

# serve frontend static files (css, js)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- auth check ---

def check_api_key(x_api_key: str = Header(None)):
    """
    Super basic API key check. Not real auth — just enough to show
    the concept of protecting endpoints. In production you'd use
    OAuth2 or something proper.
    """
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# --- request/response models ---

class AskRequest(BaseModel):
    question: str
    k: int = 4  # how many chunks to retrieve, defaults to 4

class SourceChunk(BaseModel):
    content: str
    metadata: dict
    score: float

class AskResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    latency_ms: int
    provider: str | None = None


# --- endpoints ---

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    x_api_key: str = Header(None),
):
    check_api_key(x_api_key)

    # only allow pdf and txt
    fname = file.filename or "uploaded_file"
    if not fname.lower().endswith((".pdf", ".txt")):
        raise HTTPException(400, "Only .pdf and .txt files are supported")

    # save the file to data/sample_docs/
    os.makedirs(DOCS_DIR, exist_ok=True)
    dest = os.path.join(DOCS_DIR, fname)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    logger.info(f"Uploaded: {fname}")

    # run ingestion on just this file's directory
    # TODO: ideally we'd ingest just the one file, not re-scan the whole dir.
    # But for now this works and ChromaDB handles duplicates.
    t0 = time.time()
    run_ingest()
    elapsed_ms = int((time.time() - t0) * 1000)

    return {
        "status": "ok",
        "filename": fname,
        "message": f"Ingested in {elapsed_ms}ms",
    }


@app.post("/ask", response_model=AskResponse)
async def ask_question(
    req: AskRequest,
    x_api_key: str = Header(None),
):
    check_api_key(x_api_key)

    logger.info(f"Question: {req.question}")
    t0 = time.time()

    result = ask(req.question, k=req.k)

    latency_ms = int((time.time() - t0) * 1000)

    logger.info(
        f"Answered in {latency_ms}ms | "
        f"chunks retrieved: {len(result['sources'])} | "
        f"answer length: {len(result['answer'])} chars"
    )

    return AskResponse(
        answer=result["answer"],
        sources=[SourceChunk(**s) for s in result["sources"]],
        latency_ms=latency_ms,
        provider=result.get("provider"),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the chat frontend at the root URL."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Cortex API is running. Visit /docs for API documentation."}
