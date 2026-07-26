"""
Evaluation script using Ragas.

Runs each test question through the full RAG pipeline,
then scores faithfulness and context precision using Groq as judge.

We skip answer_relevancy because it requires OpenAI embeddings internally.
Instead we use faithfulness + context_precision which only need a chat LLM.

Usage: python -m eval.run_eval
"""

import json
import os
import time

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, context_precision
from langchain_groq import ChatGroq

from app.qa_chain import ask
from app.retriever import retrieve
from app.config import GROQ_API_KEY, GROQ_MODEL


QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), "test_questions.json")
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results.json")


def load_test_data():
    with open(QUESTIONS_FILE, "r") as f:
        return json.load(f)


def run_pipeline(test_data: list) -> dict:
    """
    Run each question through the RAG pipeline and collect
    the data in the format Ragas expects.
    """
    questions = []
    answers = []
    contexts = []
    ground_truths = []

    for i, item in enumerate(test_data):
        q = item["question"]
        gt = item["ground_truth"]

        print(f"  [{i+1}/{len(test_data)}] {q[:60]}...")

        result = ask(q)
        retrieved_chunks = retrieve(q)

        questions.append(q)
        answers.append(result["answer"])
        contexts.append([c["content"] for c in retrieved_chunks])
        ground_truths.append(gt)

        # small delay to avoid rate limiting on Groq free tier
        time.sleep(2)

    return {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    }


def main():
    print("\n" + "=" * 50)
    print("Cortex RAG Evaluation")
    print("=" * 50)

    # load questions
    test_data = load_test_data()
    print(f"\nLoaded {len(test_data)} test questions from {QUESTIONS_FILE}")

    # use a subset to stay within free tier rate limits
    MAX_QUESTIONS = 5
    if len(test_data) > MAX_QUESTIONS:
        print(f"Using first {MAX_QUESTIONS} questions (free tier rate limit safety)")
        test_data = test_data[:MAX_QUESTIONS]

    # run the pipeline on each question
    print(f"\nRunning RAG pipeline on {len(test_data)} questions...")
    t0 = time.time()
    pipeline_data = run_pipeline(test_data)
    pipeline_time = time.time() - t0
    print(f"\nPipeline done in {pipeline_time:.1f}s\n")

    # build a HuggingFace Dataset (Ragas requirement)
    dataset = Dataset.from_dict(pipeline_data)

    # use Groq as the judge LLM (free tier)
    judge_llm = ChatGroq(
        model=GROQ_MODEL,
        api_key=GROQ_API_KEY,
        temperature=0,
    )

    # run Ragas evaluation
    # NOTE: we skip answer_relevancy because it needs OpenAI embeddings internally.
    # faithfulness + context_precision only need a chat LLM, so Groq works fine.
    print("Running Ragas evaluation (Groq judges the answers)...")
    print("Metrics: faithfulness, context_precision")
    print("(answer_relevancy skipped — requires OpenAI embeddings)\n")

    t0 = time.time()

    # unset OPENAI_API_KEY temporarily so ragas doesn't try to use it
    original_key = os.environ.pop("OPENAI_API_KEY", None)

    try:
        result = evaluate(
            dataset,
            metrics=[faithfulness, context_precision],
            llm=judge_llm,
        )
    finally:
        # restore the key
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key

    eval_time = time.time() - t0

    # print results
    print(f"Evaluation done in {eval_time:.1f}s\n")
    print("-" * 40)
    print("RESULTS")
    print("-" * 40)

    # Ragas 0.4.x changed the API — EvaluationResult doesn't have .items()
    # Use to_pandas() to get a DataFrame, then compute means
    scores = {}
    try:
        df = result.to_pandas()
        for col in df.columns:
            if col not in ("question", "answer", "contexts", "ground_truth", "user_input", "response", "retrieved_contexts", "reference"):
                val = df[col].dropna().mean()
                if not (val != val):  # check for NaN
                    scores[col] = round(val, 4)
                    print(f"  {col:25s} {val:.4f}")
    except Exception as e:
        # fallback: try converting to dict
        try:
            result_dict = dict(result)
            for k, v in result_dict.items():
                if isinstance(v, (int, float)):
                    scores[k] = round(v, 4)
                    print(f"  {k:25s} {v:.4f}")
        except Exception:
            print(f"  Could not extract scores: {e}")
            print(f"  Raw result: {result}")

    if not scores:
        print("  No scores computed (some jobs timed out — try again later)")

    # save to file
    output = {
        "scores": scores,
        "num_questions": len(test_data),
        "pipeline_time_seconds": round(pipeline_time, 1),
        "eval_time_seconds": round(eval_time, 1),
        "judge_llm": f"groq/{GROQ_MODEL}",
    }

    with open(RESULTS_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
