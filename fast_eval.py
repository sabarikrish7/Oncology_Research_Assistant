import json
import time
from pathlib import Path
import os
import sys

# Ensure src can be imported
sys.path.append(str(Path(__file__).parent))

from src.retrieval import HybridRetriever
from src.reranking import ClinicalReranker
from eval.retrieval_metrics import calculate_hit_rate, calculate_mrr, calculate_ndcg

def main():
    eval_dir = Path("eval")
    dataset_path = eval_dir / "golden_dataset_medcpt.json"

    print(f"Loading queries from {dataset_path}")
    with open(dataset_path, "r") as f:
        dataset = json.load(f)

    retriever = HybridRetriever()
    reranker = ClinicalReranker()

    results = []
    
    print(f"Running fast evaluation on {len(dataset)} queries...")
    start_time = time.time()

    for i, item in enumerate(dataset):
        query = item["query"]
        expected_source_id = item.get("expected_source_id", "")
        
        # 1. Retrieve top 15 from HybridRetriever (like engine.py does for conceptual)
        docs = retriever.hybrid_search(query, limit=15)
        
        # 2. Rerank
        scored_docs, max_score = reranker.rerank(query, docs)
        
        # 3. Take top 6 (like RERANKED_TOP_K in config.py)
        top_docs = scored_docs[:6]
        
        retrieved_ids = [d.get("id") for d in top_docs]

        hit_rate = calculate_hit_rate(expected_source_id, retrieved_ids, k=5)
        mrr = calculate_mrr(expected_source_id, retrieved_ids)
        ndcg = calculate_ndcg(expected_source_id, retrieved_ids, k=5)
        
        results.append({
            "id": item["id"],
            "query": query,
            "expected_source_id": expected_source_id,
            "retrieved_sources": retrieved_ids,
            "hit_rate": hit_rate,
            "mrr": mrr,
            "ndcg": ndcg,
        })

    elapsed = time.time() - start_time

    avg_hit = sum(r["hit_rate"] for r in results) / len(results)
    avg_mrr = sum(r["mrr"] for r in results) / len(results)
    avg_ndcg = sum(r["ndcg"] for r in results) / len(results)

    print(f"\n--- Fast MedCPT Retrieval Metrics ---")
    print(f"Evaluation Time: {elapsed:.2f} seconds")
    print(f"Average Hit Rate@5: {avg_hit:.4f}")
    print(f"Average MRR: {avg_mrr:.4f}")
    print(f"Average nDCG@5: {avg_ndcg:.4f}")
    print(f"-------------------------------------\n")

    with open(eval_dir / "snapshot_results_medcpt.json", "w") as f:
        json.dump(results, f, indent=2)

    report_path = eval_dir / "snapshot_report_medcpt.md"
    with open(report_path, "w") as f:
        f.write("# RAG System Evaluation Report (Fast Eval)\n\n")
        f.write(f"**Total Queries:** {len(results)}\n")
        f.write(f"**Agent Execution Time:** {elapsed:.2f} seconds (Retrieval Only)\n\n")
        f.write("## Retrieval Metrics\n")
        f.write(f"- **Hit Rate@5:** {avg_hit:.2f}\n")
        f.write(f"- **Mean Reciprocal Rank (MRR):** {avg_mrr:.2f}\n")
        f.write(f"- **nDCG@5:** {avg_ndcg:.2f}\n\n")
        
        f.write("## Query Breakdown\n")
        for res in results:
            f.write(f"### {res['id']}: {res['query']}\n\n")
            f.write(f"**Expected ID:** `{res['expected_source_id']}` | **Hit@5:** {res['hit_rate']:.2f} | **MRR:** {res['mrr']:.2f}\n\n")
            f.write(f"**Retrieved Sources:** {', '.join(res.get('retrieved_sources', []))}\n\n")
            f.write("---\n\n")
if __name__ == "__main__":
    main()
