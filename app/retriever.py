"""
Retriever: connects to the persisted ChromaDB store and runs
similarity search against the embedded chunks.
"""

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from app.config import (
    EMBEDDING_MODEL,
    CHROMA_PERSIST_DIR,
    COLLECTION_NAME,
    TOP_K,
)


# cache the embedding function so we're not reloading the model every call
_embedding_fn = None

def _get_embeddings():
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
        )
    return _embedding_fn


def get_vectorstore() -> Chroma:
    """Load the existing ChromaDB collection from disk."""
    return Chroma(
        persist_directory=CHROMA_PERSIST_DIR,
        collection_name=COLLECTION_NAME,
        embedding_function=_get_embeddings(),
    )


def retrieve(query: str, k: int = TOP_K) -> list[dict]:
    """
    Takes a question, embeds it, finds the k most similar chunks.
    
    Returns a list of dicts like:
    [
        {
            "content": "chunk text...",
            "metadata": {"source": "file.pdf", "chunk_index": 3, ...},
            "score": 0.82
        },
        ...
    ]
    
    Scores are converted from L2 distance to a 0-1 similarity.
    Higher is better.
    """
    store = get_vectorstore()

    # similarity_search_with_score returns (Document, L2_distance) tuples
    # lower distance = more similar, so we convert: score = 1 / (1 + distance)
    results = store.similarity_search_with_score(query, k=k)

    chunks = []
    for doc, distance in results:
        similarity = 1.0 / (1.0 + distance)
        chunks.append({
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": round(similarity, 4),
        })

    return chunks


if __name__ == "__main__":
    # quick test — run this after you've ingested some docs
    import sys

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is RAG?"
    print(f"\nQuery: {query}\n")

    results = retrieve(query)
    for i, r in enumerate(results):
        print(f"--- Chunk {i+1} (score: {r['score']}) ---")
        print(f"Source: {r['metadata'].get('source', '?')}")
        print(r["content"][:300])
        print()
