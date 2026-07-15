import os
import json
import time
from pathlib import Path
import sys

# Ensure src can be imported
sys.path.append(str(Path(__file__).parent.parent))

from src.engine import oncology_rag_agent


def run_snapshot():
    eval_dir = Path(__file__).parent
    dataset_path = eval_dir / "dataset.json"
    results_path = eval_dir / "snapshot_results.json"
    report_path = eval_dir / "snapshot_report.md"

    print(f"Loading queries from {dataset_path}")
    with open(dataset_path, "r") as f:
        dataset = json.load(f)

    results = []

    print(f"Running Day 1 Snapshot Evaluation ({len(dataset)} queries)...")

    start_time = time.time()

    for i, item in enumerate(dataset):
        query = item["query"]
        print(f"\n[{i + 1}/{len(dataset)}] Processing: {query}")

        inputs = {"query": query, "retries": 0}

        final_generation = ""
        final_steps = []
        final_report = {}
        final_docs = []

        try:
            for output in oncology_rag_agent.stream(inputs):
                for node_name, state_update in output.items():
                    if "generation" in state_update and state_update["generation"]:
                        final_generation = state_update["generation"]
                    if "steps" in state_update:
                        final_steps = state_update["steps"]
                    if "validation_report" in state_update:
                        final_report = state_update["validation_report"]
                    if "documents" in state_update:
                        final_docs = state_update["documents"]

            result = {
                "id": item["id"],
                "query": query,
                "generation": final_generation,
                "execution_path": final_steps,
                "validation_report": final_report,
                "retrieved_sources": [
                    {
                        "id": d.get("id"),
                        "source": d.get("source"),
                        "score": d.get("score"),
                    }
                    for d in final_docs
                ],
            }
            results.append(result)
            print(
                f"  -> Generated {len(final_generation)} chars. Path: {' -> '.join(final_steps)}"
            )

        except Exception as e:
            print(f"  -> Error processing query: {e}")
            results.append({"id": item["id"], "query": query, "error": str(e)})

    elapsed_time = time.time() - start_time
    print(f"\nFinished in {elapsed_time:.2f} seconds.")

    print(f"Saving results to {results_path}")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Generating report to {report_path}")
    with open(report_path, "w") as f:
        f.write("# Day 1 Snapshot Evaluation Report\n\n")
        f.write(f"**Total Queries:** {len(dataset)}\n")
        f.write(f"**Execution Time:** {elapsed_time:.2f} seconds\n\n")

        for res in results:
            f.write(f"## {res['id']}: {res['query']}\n\n")
            if "error" in res:
                f.write(f"**ERROR:** {res['error']}\n\n")
                continue

            f.write(f"**Execution Path:** `{' ➔ '.join(res['execution_path'])}`\n\n")

            # Formatted sources
            sources_str = ", ".join(
                [f"[{s['source']}: {s['id']}]" for s in res["retrieved_sources"]]
            )
            f.write(
                f"**Retrieved Sources:** {sources_str if sources_str else 'None'}\n\n"
            )

            # Validation Metrics
            if res["validation_report"]:
                is_safe = res["validation_report"].get("is_safe_to_display", False)
                f.write(f"**Validation:** {'✅ PASS' if is_safe else '❌ FAIL'}\n\n")

            f.write("### Answer\n\n")
            f.write(f"> {res['generation']}\n\n")
            f.write("---\n\n")


if __name__ == "__main__":
    run_snapshot()
