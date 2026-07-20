import json
from src.retrieval import HybridRetriever

QUERIES = [
    "KRAS G12C inhibitors in NSCLC",
    "recent HER2-low trials",
    "Trastuzumab deruxtecan usage",
    "BRCA1 mutations risk reducing mastectomy",
    "management of chemotherapy-induced neuropathy",
    "PARP inhibitors maintenance in ovarian cancer",
    "PD-L1 testing for immune checkpoint blockade",
    "CDK4/6 inhibitors combined with endocrine therapy",
    "EGFR exon 20 insertion mutations targeted therapy",
    "Adjuvant treatment for high-risk melanoma"
]

def run_benchmark():
    retriever = HybridRetriever()
    results = {}
    
    for q in QUERIES:
        # Get top 5 semantic search results (bypass hybrid RRF to test raw dense performance)
        hits = retriever.search(q, limit=5)
        # Store just the source and ID and a snippet for brevity
        results[q] = [{"source": h["source"], "id": h["id"], "snippet": h["text"][:100]} for h in hits]
        
    return results

if __name__ == "__main__":
    baseline = run_benchmark()
    with open("baseline.json", "w") as f:
        json.dump(baseline, f, indent=2)
    print("Benchmark complete. Results saved to baseline.json.")
