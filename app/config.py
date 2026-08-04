import os
from dotenv import load_dotenv

load_dotenv()

# Render mounts persistent disks at /data — use that if available.
# Falls back to local paths for development.
if os.path.isdir("/data"):
    CHROMA_PERSIST_DIR = "/data/chroma_db"
    DOCS_DIR = "/data/sample_docs"
else:
    CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
    DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sample_docs")

COLLECTION_NAME = "cortex_docs"

# Chunking params — these are character counts, not tokens.
# Rule of thumb: 1 token ≈ 4 chars for English, so 1500 chars ≈ 375 tokens.
# I originally wanted 500 tokens but bumped the char count up a bit
# because the splitter sometimes makes smaller chunks than you'd expect.
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

# --- LLM config ---
# Add as many provider keys as you have. The system tries them in order
# and automatically falls back to the next one if quota runs out.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")

OPENAI_MODEL = "gpt-4o-mini"
GEMINI_MODEL = "gemini-2.0-flash-lite"
GROQ_MODEL = "llama-3.1-8b-instant"  # free tier on Groq
HF_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"  # free on HF Inference API

# --- Retrieval ---
TOP_K = 4

# --- API ---
API_KEY = os.getenv("CORTEX_API_KEY", "")
