import os
import json
import time
from pathlib import Path
import sys

# Ensure src can be imported
sys.path.append(str(Path(__file__).parent.parent))

from src.engine import oncology_rag_agent
from eval.retrieval_metrics import calculate_hit_rate, calculate_mrr, calculate_ndcg

import json
from datasets import Dataset
from ragas import evaluate
from ragas.metrics.collections import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_ollama import ChatOllama
from langchain_community.embeddings import HuggingFaceEmbeddings

def run_evaluation():
    eval_dir = Path(__file__).parent
    dataset_path = eval_dir / "golden_dataset.json"
    results_path = eval_dir / "snapshot_results.json"
    report_path = eval_dir / "snapshot_report.md"

    print(f"Loading queries from {dataset_path}")
    if not dataset_path.exists():
        print("Golden dataset not found. Please run generate_golden_dataset.py first.")
        return

    with open(dataset_path, "r") as f:
        dataset = json.load(f)

    # We will accumulate results for RAGAS and custom retrieval metrics
    results = []
    ragas_data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": []
    }

    print(f"Running Evaluation on {len(dataset)} queries...")
    start_time = time.time()

    # RAGAS configuration
    eval_llm = ChatOllama(model="llama3")
    eval_embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-large-en-v1.5",
        model_kwargs={'device': 'cpu'}
    )

    for i, item in enumerate(dataset):
        query = item["query"]
        expected_source_id = item.get("expected_source_id", "")
        ground_truth = item.get("ground_truth", "")

        print(f"\n[{i + 1}/{len(dataset)}] Processing: {query}")

        inputs = {"query": query, "retries": 0}
        final_generation = ""
        final_steps = []
        final_docs = []

        try:
            for output in oncology_rag_agent.stream(inputs):
                for node_name, state_update in output.items():
                    if "generation" in state_update and state_update["generation"]:
                        final_generation = state_update["generation"]
                    if "steps" in state_update:
                        final_steps = state_update["steps"]
                    if "documents" in state_update:
                        final_docs = state_update["documents"]

            retrieved_ids = [d.get("id") for d in final_docs]
            retrieved_texts = [d.get("text", "") for d in final_docs]

            # Calculate custom retrieval metrics
            hit_rate = calculate_hit_rate(expected_source_id, retrieved_ids, k=5)
            mrr = calculate_mrr(expected_source_id, retrieved_ids)
            ndcg = calculate_ndcg(expected_source_id, retrieved_ids, k=5)

            result = {
                "id": item["id"],
                "query": query,
                "expected_source_id": expected_source_id,
                "hit_rate_at_5": hit_rate,
                "mrr": mrr,
                "ndcg_at_5": ndcg,
                "generation": final_generation,
                "execution_path": final_steps,
                "retrieved_sources": retrieved_ids
            }
            results.append(result)

            # Append to ragas data format
            ragas_data["question"].append(query)
            ragas_data["answer"].append(str(final_generation))
            ragas_data["contexts"].append(retrieved_texts)
            
            # Sanitize ground_truth to string to avoid pyarrow mix type error
            if isinstance(ground_truth, list):
                ground_truth = " ".join([str(v) for v in ground_truth])
            elif isinstance(ground_truth, dict):
                ground_truth = json.dumps(ground_truth)
            ragas_data["ground_truth"].append(str(ground_truth))

            print(f"  -> Generated {len(final_generation)} chars. Hit@5: {hit_rate}, MRR: {mrr:.2f}")

        except Exception as e:
            print(f"  -> Error processing query: {e}")
            results.append({"id": item["id"], "query": query, "error": str(e)})

    elapsed_time = time.time() - start_time
    print(f"\nAgent execution finished in {elapsed_time:.2f} seconds.")

    # Calculate aggregate retrieval metrics
    valid_results = [r for r in results if "error" not in r]
    avg_hit_rate = sum(r["hit_rate_at_5"] for r in valid_results) / len(valid_results) if valid_results else 0
    avg_mrr = sum(r["mrr"] for r in valid_results) / len(valid_results) if valid_results else 0
    avg_ndcg = sum(r["ndcg_at_5"] for r in valid_results) / len(valid_results) if valid_results else 0

    print(f"\n--- Retrieval Metrics ---")
    print(f"Average Hit Rate@5: {avg_hit_rate:.2f}")
    print(f"Average MRR: {avg_mrr:.2f}")
    print(f"Average nDCG@5: {avg_ndcg:.2f}")
    print(f"-------------------------\n")

    print("Saving checkpoint...")
    with open("eval/ragas_data_checkpoint.json", "w") as f:
        json.dump(ragas_data, f, indent=2)

    print("Running RAGAS Evaluation...")
    ragas_dataset = Dataset.from_dict(ragas_data)
    ragas_llm = LangchainLLMWrapper(eval_llm)
    ragas_emb = LangchainEmbeddingsWrapper(eval_embeddings)
    ragas_results = None
    try:
        ragas_results = evaluate(
            ragas_dataset,
            metrics=[faithfulness(), answer_relevancy(), context_precision(), context_recall()],
            llm=ragas_llm,
            embeddings=ragas_emb
        )
        print("RAGAS Results:", ragas_results)
    except Exception as e:
        print(f"RAGAS evaluation failed: {e}")

    print(f"Saving results to {results_path}")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Generating report to {report_path}")
    with open(report_path, "w") as f:
        f.write("# RAG System Evaluation Report\n\n")
        f.write(f"**Total Queries:** {len(valid_results)}\n")
        f.write(f"**Agent Execution Time:** {elapsed_time:.2f} seconds\n\n")

        f.write("## Retrieval Metrics\n")
        f.write(f"- **Hit Rate@5:** {avg_hit_rate:.2f}\n")
        f.write(f"- **Mean Reciprocal Rank (MRR):** {avg_mrr:.2f}\n")
        f.write(f"- **nDCG@5:** {avg_ndcg:.2f}\n\n")

        if ragas_results:
            f.write("## RAGAS Generation Metrics\n")
            for metric_name, score in ragas_results.items():
                f.write(f"- **{metric_name}:** {score:.4f}\n")
            f.write("\n")

        f.write("## Query Breakdown\n")
        for res in results:
            f.write(f"### {res['id']}: {res['query']}\n\n")
            if "error" in res:
                f.write(f"**ERROR:** {res['error']}\n\n")
                continue

            f.write(f"**Expected ID:** `{res['expected_source_id']}` | **Hit@5:** {res['hit_rate_at_5']} | **MRR:** {res['mrr']:.2f}\n\n")
            f.write(f"**Execution Path:** `{' ➔ '.join(res['execution_path'])}`\n\n")
            f.write(f"**Retrieved Sources:** {', '.join(res['retrieved_sources'])}\n\n")
            f.write("#### Generated Answer\n\n")
            f.write(f"> {res['generation']}\n\n")
            f.write("---\n\n")

if __name__ == "__main__":
    run_evaluation()
