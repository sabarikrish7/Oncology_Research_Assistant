import json
import os
import math
from pathlib import Path

eval_dir = Path("eval")
with open(eval_dir / "golden_dataset_medcpt.json") as f:
    golden = json.load(f)

golden_map = {item["query"]: item.get("expected_source_id", "") for item in golden}

with open(eval_dir / "snapshot_results_medcpt.json") as f:
    results = json.load(f)

def calculate_hit_rate(expected_id, retrieved_ids, k=5):
    return 1 if expected_id in retrieved_ids[:k] else 0

def calculate_mrr(expected_id, retrieved_ids):
    try:
        rank = retrieved_ids.index(expected_id) + 1
        return 1.0 / rank
    except ValueError:
        return 0.0

def calculate_ndcg(expected_id, retrieved_ids, k=5):
    if expected_id in retrieved_ids[:k]:
        rank = retrieved_ids.index(expected_id) + 1
        return 1.0 / math.log2(rank + 1)
    return 0.0

valid_results = []
for res in results:
    query = res["query"]
    if query in golden_map:
        expected_id = golden_map[query]
        res["expected_source_id"] = expected_id
        retrieved_ids = res.get("retrieved_sources", [])
        res["hit_rate_at_5"] = calculate_hit_rate(expected_id, retrieved_ids, k=5)
        res["mrr"] = calculate_mrr(expected_id, retrieved_ids)
        res["ndcg_at_5"] = calculate_ndcg(expected_id, retrieved_ids, k=5)
    valid_results.append(res)

with open(eval_dir / "snapshot_results_medcpt.json", "w") as f:
    json.dump(valid_results, f, indent=2)

avg_hit_rate = sum(r["hit_rate_at_5"] for r in valid_results) / len(valid_results) if valid_results else 0
avg_mrr = sum(r["mrr"] for r in valid_results) / len(valid_results) if valid_results else 0
avg_ndcg = sum(r["ndcg_at_5"] for r in valid_results) / len(valid_results) if valid_results else 0

print(f"Metrics recalculated:")
print(f"Avg Hit Rate@5: {avg_hit_rate:.4f}")
print(f"Avg MRR: {avg_mrr:.4f}")
print(f"Avg nDCG@5: {avg_ndcg:.4f}")

report_path = eval_dir / "snapshot_report_medcpt.md"
with open(report_path, "w") as f:
    f.write("# RAG System Evaluation Report\n\n")
    f.write(f"**Total Queries:** {len(valid_results)}\n")
    f.write(f"**Agent Execution Time:** 1942.34 seconds (recalculated)\n\n")
    f.write("## Retrieval Metrics\n")
    f.write(f"- **Hit Rate@5:** {avg_hit_rate:.2f}\n")
    f.write(f"- **Mean Reciprocal Rank (MRR):** {avg_mrr:.2f}\n")
    f.write(f"- **nDCG@5:** {avg_ndcg:.2f}\n\n")
    
    f.write("## Query Breakdown\n")
    for res in valid_results:
        f.write(f"### {res['id']}: {res['query']}\n\n")
        if "error" in res:
            f.write(f"**ERROR:** {res['error']}\n\n")
            continue
        
        f.write(f"**Expected ID:** `{res['expected_source_id']}` | **Hit@5:** {res['hit_rate_at_5']} | **MRR:** {res['mrr']:.2f}\n\n")
        f.write(f"**Execution Path:** `{' ➔ '.join(res.get('execution_path', []))}`\n\n")
        f.write(f"**Retrieved Sources:** {', '.join(res.get('retrieved_sources', []))}\n\n")
        f.write("#### Generated Answer\n\n")
        f.write(f"> {res.get('generation', '')}\n\n")
        f.write("---\n\n")
