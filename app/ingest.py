"""
Ingestion pipeline: loads documents from data/sample_docs/,
splits them into chunks, embeds with sentence-transformers,
and stores everything in ChromaDB.

Run standalone:  python -m app.ingest
"""

import os
import sys
import time
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from app.config import (
    EMBEDDING_MODEL,
    CHROMA_PERSIST_DIR,
    COLLECTION_NAME,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    DOCS_DIR,
)


def load_documents(docs_dir: str) -> list:
    """
    Walk through docs_dir and load every .pdf and .txt file.
    Returns a flat list of LangChain Document objects.
    """
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        print(f"[ingest] Directory not found: {docs_dir}")
        return []

    all_docs = []
    files = list(docs_path.iterdir())

    for fpath in files:
        suffix = fpath.suffix.lower()
        try:
            if suffix == ".pdf":
                loader = PyPDFLoader(str(fpath))
                loaded = loader.load()
            elif suffix == ".txt":
                loader = TextLoader(str(fpath), encoding="utf-8")
                loaded = loader.load()
            else:
                continue  # skip anything that's not pdf/txt

            print(f"  loaded {fpath.name}  ({len(loaded)} page(s)/section(s))")
            all_docs.extend(loaded)

        except Exception as e:
            # don't crash the whole pipeline because one file is wonky
            print(f"  [WARN] skipping {fpath.name}: {e}")

    return all_docs


def chunk_documents(docs: list) -> list:
    """
    Split documents into smaller chunks for embedding.
    
    Using RecursiveCharacterTextSplitter because it tries to split
    on natural boundaries (paragraphs, sentences, words) before
    falling back to raw character splits. This keeps chunks more
    semantically coherent than a naive fixed-window approach.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,  # counting characters, not tokens
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_documents(docs)

    # tag each chunk with its index so we can trace back later
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
        # source filename is already set by the loaders,
        # but let's make it just the basename for readability
        if "source" in chunk.metadata:
            chunk.metadata["source"] = os.path.basename(chunk.metadata["source"])

    return chunks


def get_embedding_fn():
    """Return the embedding function. Downloads model on first run (~80MB)."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},  # TODO: detect GPU if available
    )


def store_chunks(chunks: list, embedding_fn) -> Chroma:
    """
    Embed all chunks and persist to ChromaDB.
    If the collection already exists on disk, this will add to it
    (Chroma deduplicates by document ID automatically).
    """
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_fn,
        persist_directory=CHROMA_PERSIST_DIR,
        collection_name=COLLECTION_NAME,
    )
    return vectorstore


def run_ingest(docs_dir: str = None):
    """Full ingestion pipeline — call this from the API or from __main__."""
    target_dir = docs_dir or DOCS_DIR

    print(f"\n{'='*50}")
    print(f"[ingest] Starting ingestion from: {target_dir}")
    print(f"{'='*50}\n")

    t0 = time.time()

    # 1. load
    print("[ingest] Loading documents...")
    docs = load_documents(target_dir)
    if not docs:
        print("[ingest] No documents found. Put PDFs or .txt files in data/sample_docs/")
        return None
    print(f"[ingest] Loaded {len(docs)} document section(s) total\n")

    # 2. chunk
    print("[ingest] Splitting into chunks...")
    chunks = chunk_documents(docs)
    print(f"[ingest] Created {len(chunks)} chunks "
          f"(chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})\n")

    # 3. embed + store
    print("[ingest] Embedding and storing in ChromaDB...")
    print(f"  (model: {EMBEDDING_MODEL})")
    print(f"  (persist dir: {CHROMA_PERSIST_DIR})")
    embedding_fn = get_embedding_fn()
    vectorstore = store_chunks(chunks, embedding_fn)

    elapsed = time.time() - t0
    print(f"\n[ingest] Done! {len(chunks)} chunks indexed in {elapsed:.1f}s")

    # quick sanity check
    count = vectorstore._collection.count()
    print(f"[ingest] ChromaDB collection '{COLLECTION_NAME}' now has {count} documents")

    return vectorstore


if __name__ == "__main__":
    run_ingest()
