"""
QA chain: takes a user question, retrieves relevant chunks,
builds a grounded prompt, and sends it to an LLM for an answer.

Supports OpenAI, Google Gemini, and Groq. If one provider's quota
runs out or errors, it automatically tries the next one.
"""

import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import (
    OPENAI_API_KEY, OPENAI_MODEL,
    GOOGLE_API_KEY, GEMINI_MODEL,
    GROQ_API_KEY, GROQ_MODEL,
    HF_TOKEN, HF_MODEL,
)
from app.retriever import retrieve

logger = logging.getLogger("cortex")


SYSTEM_PROMPT = """You are a helpful assistant that answers questions based ONLY on the provided context.

Rules:
- Answer the question using ONLY the information in the context below.
- If the context does not contain enough information to answer, say "I don't have enough information in the provided documents to answer that."
- Do not make up facts or use knowledge from outside the context.
- Keep answers concise but complete.
- If relevant, mention which source document the information comes from.

Context:
{context}"""

USER_PROMPT = "{question}"


def _get_available_llms(custom_keys: dict = None):
    """
    Build a list of (name, llm_instance) for every provider that has a key set.
    Supports user-provided keys passed per request (BYOK) with fallback to env vars.
    Order: Groq (free, fast) → Gemini (free) → HuggingFace (free) → OpenAI (paid).
    """
    custom_keys = custom_keys or {}
    llms = []

    groq_key = custom_keys.get("groq") or GROQ_API_KEY
    if groq_key:
        from langchain_groq import ChatGroq
        llms.append(("groq", ChatGroq(
            model=GROQ_MODEL,
            api_key=groq_key,
            temperature=0,
        )))

    gemini_key = custom_keys.get("gemini") or GOOGLE_API_KEY
    if gemini_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llms.append(("gemini", ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=gemini_key,
            temperature=0,
        )))

    hf_token = custom_keys.get("huggingface") or HF_TOKEN
    if hf_token:
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
        hf_endpoint = HuggingFaceEndpoint(
            repo_id=HF_MODEL,
            huggingfacehub_api_token=hf_token,
            temperature=0.01,  # HF doesn't like exact 0
            max_new_tokens=512,
        )
        llms.append(("huggingface", ChatHuggingFace(
            llm=hf_endpoint,
        )))

    openai_key = custom_keys.get("openai") or OPENAI_API_KEY
    if openai_key:
        from langchain_openai import ChatOpenAI
        llms.append(("openai", ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=openai_key,
            temperature=0,
        )))

    return llms


def build_context_block(chunks: list[dict]) -> str:
    """Format retrieved chunks into a single context string for the prompt."""
    parts = []
    for i, chunk in enumerate(chunks):
        source = chunk["metadata"].get("source", "unknown")
        parts.append(f"[Source: {source}]\n{chunk['content']}")
    return "\n\n---\n\n".join(parts)


def ask(question: str, k: int = 4, custom_keys: dict = None) -> dict:
    """
    End-to-end: retrieve chunks, build prompt, call LLM, return answer + sources.
    
    Tries each configured provider in order. If one fails (quota exceeded,
    rate limit, network error), falls back to the next.
    """
    # 1. retrieve
    chunks = retrieve(question, k=k)

    if not chunks:
        return {
            "answer": "No relevant documents found. Have you ingested any documents yet?",
            "sources": [],
            "provider": None,
        }

    # 2. build the prompt
    context_text = build_context_block(chunks)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    # 3. try each LLM provider until one works
    available = _get_available_llms(custom_keys=custom_keys)

    if not available:
        return {
            "answer": "No LLM API keys provided. Please enter at least one API key (Groq, Gemini, HuggingFace, or OpenAI) in the settings.",
            "sources": chunks,
            "provider": None,
        }

    last_error = None
    for provider_name, llm in available:
        try:
            logger.info(f"Trying provider: {provider_name}")
            chain = prompt | llm | StrOutputParser()
            answer = chain.invoke({
                "context": context_text,
                "question": question,
            })
            logger.info(f"Success with: {provider_name}")
            return {
                "answer": answer,
                "sources": chunks,
                "provider": provider_name,
            }
        except Exception as e:
            last_error = e
            logger.warning(f"Provider {provider_name} failed: {e}")
            continue  # try the next one

    # all providers failed
    return {
        "answer": f"All LLM providers failed. Last error: {last_error}",
        "sources": chunks,
        "provider": None,
    }


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is RAG?"
    print(f"\nQuestion: {q}\n")

    result = ask(q)
    print(f"Provider: {result.get('provider', '?')}")
    print(f"Answer: {result['answer']}\n")
    print(f"Based on {len(result['sources'])} source chunk(s):")
    for s in result["sources"]:
        print(f"  - {s['metadata'].get('source', '?')} (score: {s['score']})")
