import json
import time
from pathlib import Path
import sys

# Ensure src can be imported
sys.path.append(str(Path(__file__).parent.parent))

from src.retrieval import HybridRetriever
from eval.retrieval_metrics import calculate_hit_rate, calculate_mrr, calculate_ndcg

def run_quick_eval():
    dataset_path = Path(__file__).parent / "golden_dataset.json"
    if not dataset_path.exists():
        print("Dataset not found!")
        return

    with open(dataset_path, "r") as f:
        dataset = json.load(f)

    print(f"Loaded {len(dataset)} queries.")
    
    retriever = HybridRetriever()
    
    results = []
    start_time = time.time()
    
    for i, item in enumerate(dataset):
        query = item["query"]
        expected_source_id = item.get("expected_source_id", "")
        
        # Retrieve docs
        docs = retriever.search(query, limit=5)
        retrieved_ids = [d.get("id") for d in docs]
        
        hit_rate = calculate_hit_rate(expected_source_id, retrieved_ids, k=5)
        mrr = calculate_mrr(expected_source_id, retrieved_ids)
        ndcg = calculate_ndcg(expected_source_id, retrieved_ids, k=5)
        
        results.append({
            "hit_rate": hit_rate,
            "mrr": mrr,
            "ndcg": ndcg
        })
        print(f"[{i+1}/50] Hit@5: {hit_rate}, MRR: {mrr:.2f}")

    elapsed_time = time.time() - start_time
    
    avg_hit_rate = sum(r["hit_rate"] for r in results) / len(results)
    avg_mrr = sum(r["mrr"] for r in results) / len(results)
    avg_ndcg = sum(r["ndcg"] for r in results) / len(results)

    print(f"\n--- Quick Eval Metrics (BGE-Large) ---")
    print(f"Average Hit Rate@5: {avg_hit_rate:.2f}")
    print(f"Average MRR: {avg_mrr:.2f}")
    print(f"Average nDCG@5: {avg_ndcg:.2f}")
    print(f"Total Time: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    run_quick_eval()
