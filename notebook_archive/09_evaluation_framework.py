import json
import ollama
import numpy as np
import pandas as pd
from typing import List, Dict


class RagasCustomEvaluator:
    """Mimics the RAGAS framework using local Llama 3 to evaluate Answer Relevancy and Faithfulness."""

    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name

    def evaluate_faithfulness(self, question: str, answer: str, context: str) -> float:
        """Checks if the generated answer can be entirely deduced from the context."""
        prompt = f"""Given the following context, is the generated answer fully supported by the context without adding external information?
Context: {context}
Answer: {answer}
Output strictly a valid JSON object: {{"supported": 1}} if yes, {{"supported": 0}} if it contains hallucinations or outside knowledge."""

        try:
            response = ollama.chat(
                model=self.model_name, messages=[{"role": "user", "content": prompt}]
            )
            res_text = response["message"]["content"].strip()
            # Simple parsing
            if "1" in res_text:
                return 1.0
            return 0.0
        except:
            return 0.0

    def evaluate_relevancy(self, question: str, answer: str) -> float:
        """Checks if the answer directly addresses the user's question."""
        prompt = f"""Does the following answer directly and adequately answer the question?
Question: {question}
Answer: {answer}
Output strictly a valid JSON object: {{"relevant": 1}} if yes, {{"relevant": 0}} if it is evasive or off-topic."""

        try:
            response = ollama.chat(
                model=self.model_name, messages=[{"role": "user", "content": prompt}]
            )
            res_text = response["message"]["content"].strip()
            if "1" in res_text:
                return 1.0
            return 0.0
        except:
            return 0.0


class RetrievalEvaluator:
    """Calculates standard search engine metrics: MRR, Precision, Hit Rate."""

    @staticmethod
    def calculate_mrr(retrieved_ids: List[str], ground_truth_id: str) -> float:
        for rank, doc_id in enumerate(retrieved_ids):
            if doc_id == ground_truth_id:
                return 1.0 / (rank + 1)
        return 0.0

    @staticmethod
    def calculate_hit_rate(retrieved_ids: List[str], ground_truth_id: str) -> float:
        return 1.0 if ground_truth_id in retrieved_ids else 0.0


# --- BENCHMARK EXECUTION ---
if __name__ == "__main__":
    print("Initializing Phase 9 Evaluation Suite...\n")

    ragas_eval = RagasCustomEvaluator()
    retrieval_eval = RetrievalEvaluator()

    # Simulated Benchmark Dataset (Testing our pipeline's historical performance)
    benchmark_dataset = [
        {
            "query": "What is the targeted therapy for KRAS G12C?",
            "ground_truth_id": "PMID_111",
            "retrieved_ids": ["PMID_111", "NCCN_2", "PMID_404"],
            "context": "Sotorasib is indicated for advanced NSCLC with KRAS G12C mutations.",
            "generated_answer": "Sotorasib is a targeted therapy used for patients with KRAS G12C mutated non-small cell lung cancer [PMID_111].",
        },
        {
            "query": "Is trastuzumab used for HER2-negative breast cancer?",
            "ground_truth_id": "NCCN_B1",
            "retrieved_ids": [
                "NCCN_B2",
                "NCCN_B1",
                "PMID_99",
            ],  # Found it, but at rank 2
            "context": "Trastuzumab is indicated exclusively for HER2-positive breast cancer. It is not effective in HER2-negative subtypes.",
            "generated_answer": "No, trastuzumab is only indicated for HER2-positive breast cancer [NCCN_B1].",
        },
        {
            "query": "What is the survival rate for stage 4 melanoma?",
            "ground_truth_id": "SEER_2023",
            "retrieved_ids": [
                "PMID_A",
                "PMID_B",
                "PMID_C",
            ],  # Failed to retrieve the ground truth
            "context": "General treatment involves immunotherapy. No specific survival statistics are mentioned in this text.",
            "generated_answer": "The 5-year survival rate for stage 4 melanoma is 30% [SEER_2023].",  # Hallucinated answer
        },
    ]

    results = []

    print("Running evaluations across dataset...")
    for idx, data in enumerate(benchmark_dataset):
        print(f"Evaluating Sample {idx + 1}/{len(benchmark_dataset)}...")

        # 1. Retrieval Metrics
        mrr = retrieval_eval.calculate_mrr(
            data["retrieved_ids"], data["ground_truth_id"]
        )
        hit_rate = retrieval_eval.calculate_hit_rate(
            data["retrieved_ids"], data["ground_truth_id"]
        )

        # 2. RAGAS Generation Metrics
        faithfulness = ragas_eval.evaluate_faithfulness(
            data["query"], data["generated_answer"], data["context"]
        )
        relevancy = ragas_eval.evaluate_relevancy(
            data["query"], data["generated_answer"]
        )

        results.append(
            {
                "Query": data["query"][:30] + "...",
                "MRR": round(mrr, 2),
                "Hit Rate": hit_rate,
                "Faithfulness": faithfulness,
                "Relevancy": relevancy,
            }
        )

    # Aggregate and Display Report
    df_results = pd.DataFrame(results)

    print("\n=======================================================")
    print("PHASE 9: SYSTEM EVALUATION BENCHMARK REPORT")
    print("=======================================================\n")

    # Calculate System Averages
    print("--- OVERALL SYSTEM QUALITY ---")
    print(f"Mean Reciprocal Rank (MRR):  {df_results['MRR'].mean():.2f}")
    print(f"Overall Hit Rate:            {df_results['Hit Rate'].mean():.2f}")
    print(f"System Faithfulness Score:   {df_results['Faithfulness'].mean():.2f}")
    print(f"System Answer Relevancy:     {df_results['Relevancy'].mean():.2f}")

    print("\n--- SAMPLE-BY-SAMPLE BREAKDOWN ---")
    print(df_results.to_string(index=False))
