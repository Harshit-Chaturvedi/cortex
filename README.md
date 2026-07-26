# Cortex

A RAG (Retrieval-Augmented Generation) Q&A assistant. Upload documents, ask questions, get answers that are actually grounded in what the documents say — not hallucinated.

I built this to understand how RAG works end-to-end: from chunking and embedding documents to retrieving relevant context and generating answers with an LLM. It's not production-ready, but it works, and I can explain every piece of it.

## What it does

1. You upload PDFs or text files
2. The system splits them into chunks, embeds them with a local model, and stores the vectors in ChromaDB
3. When you ask a question, it finds the most relevant chunks via similarity search
4. Those chunks get fed into a prompt that tells the LLM to answer *only* from the provided context
5. You get back the answer plus the source chunks it used

The point is that the LLM can't make stuff up — it either finds the answer in your documents or tells you it doesn't know.

## Architecture

```
 Upload PDF/TXT
       │
       ▼
 PyPDF / TextLoader
       │
       ▼
 RecursiveCharacterTextSplitter (2000 chars, 200 overlap)
       │
       ▼
 SentenceTransformer Embedding (all-MiniLM-L6-v2, local)
       │
       ▼
   ChromaDB (persisted to disk)
       │
       │  User Question
       │       │
       │       ▼
       │  Embed Query
       │       │
       └───────┤
               ▼
        Top-K Similarity Search
               │
               ▼
        Prompt Builder (grounded context)
               │
               ▼
        LLM (auto-fallback: Groq → Gemini → HuggingFace → OpenAI)
               │
               ▼
        Answer + Sources + Provider info
```

## Multi-provider LLM fallback

Cortex doesn't depend on a single LLM provider. It tries them in order and automatically falls back if one runs out of quota or errors:

| Order | Provider | Cost | Model |
|-------|----------|------|-------|
| 1st | **Groq** | Free tier | llama-3.1-8b-instant |
| 2nd | **Google Gemini** | Free tier | gemini-2.0-flash-lite |
| 3rd | **HuggingFace** | Free tier | Mistral-7B-Instruct-v0.3 |
| 4th | **OpenAI** | Paid | gpt-4o-mini |

You only need **one** working key. The more you add, the more resilient it is.

## Tech stack

- **Python 3.11+**
- **LangChain** — orchestration (document loading, splitting, LLM chain)
- **ChromaDB** — local vector database, persisted to disk
- **Sentence-Transformers** (all-MiniLM-L6-v2) — free, local embedding model
- **FastAPI** — API layer with Swagger docs
- **Ragas** — automated evaluation (faithfulness, context precision)
- **Docker** — containerization

## Setup

```bash
# clone and cd in
git clone https://github.com/YOUR_USERNAME/cortex.git
cd cortex

# create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

# install dependencies
pip install -r requirements.txt

# set up your env vars
copy .env.example .env        # Windows
# cp .env.example .env        # Mac/Linux
```

Then edit `.env` and add at least one API key. All are free:

| Provider | Where to get the key |
|----------|---------------------|
| Groq | [console.groq.com/keys](https://console.groq.com/keys) |
| Gemini | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| HuggingFace | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| OpenAI | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) (paid) |

## Usage

### 1. Ingest documents

Drop your PDFs and/or .txt files into `data/sample_docs/`, then:

```bash
python -m app.ingest
```

This loads, chunks, embeds, and stores everything in ChromaDB. A sample doc is included to get you started.

### 2. Start the API

```bash
uvicorn app.main:app --reload
```

Server starts at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 3. Ask a question

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-change-me" \
  -d '{"question": "What is RAG?"}'
```

### 4. Upload a document via API

```bash
curl -X POST http://localhost:8000/upload \
  -H "X-API-Key: dev-key-change-me" \
  -F "file=@my_document.pdf"
```

### Example response

```json
{
  "answer": "RAG (Retrieval-Augmented Generation) is a technique that enhances large language models by grounding their responses in external knowledge retrieved at query time.",
  "sources": [
    {
      "content": "Retrieval-Augmented Generation (RAG) is a technique...",
      "metadata": { "source": "rag_overview.txt", "chunk_index": 0 },
      "score": 0.4381
    }
  ],
  "latency_ms": 4348,
  "provider": "groq"
}
```

## Docker

```bash
# build and run
docker compose up --build

# or just docker
docker build -t cortex .
docker run -p 8000:8000 --env-file .env cortex
```

## Evaluation

The eval script runs test questions through the full pipeline and scores the results using Ragas (with Groq as the judge LLM — no OpenAI needed):

```bash
python -m eval.run_eval
```

Metrics measured:
- **Faithfulness** — did the answer stick to the context or hallucinate?
- **Context Precision** — were the retrieved chunks actually useful?

Results get saved to `eval/results.json`. My latest run scored **context_precision: 1.0** (perfect retrieval).

## Project structure

```
cortex/
├── app/
│   ├── config.py         # settings, env vars, provider config
│   ├── ingest.py         # document loading, chunking, embedding
│   ├── retriever.py      # vector similarity search
│   ├── qa_chain.py       # multi-provider LLM fallback + prompt
│   └── main.py           # FastAPI endpoints
├── data/
│   └── sample_docs/      # drop your documents here
├── eval/
│   ├── test_questions.json  # 18 test Q&A pairs
│   └── run_eval.py       # Ragas evaluation script
├── chroma_db/            # vector store (gitignored, regenerated)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Things I'd improve next

- **Streaming responses.** The `/ask` endpoint waits for the full answer before responding. Streaming would show tokens as they're generated.
- **Better PDF handling.** PyPDFLoader is basic — it struggles with tables and multi-column layouts. Something like Unstructured or pdfplumber would be better.
- **Hybrid search.** Pure vector similarity sometimes misses keyword-heavy queries. Combining with BM25 would catch those.
- **A frontend.** Right now it's API-only. A simple chat interface would make it demo better.
- **Chunk size tuning.** I picked 2000 characters as a starting point. You'd experiment with different sizes per doc type.
- **Proper auth.** The current API key check is a string comparison. Fine for a prototype, not for production.
