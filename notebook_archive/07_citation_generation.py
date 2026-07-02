import json
import requests
import ollama
from typing import List, Literal, TypedDict
from sentence_transformers import CrossEncoder
from langgraph.graph import StateGraph, END

# --- STATE SCHEMA ---
class GraphState(TypedDict):
    query: str
    route: str
    documents: List[dict]
    generation: str
    steps: List[str]

# --- RE-USE PHASE 5 & 6 LOGIC ---
class LiveEvidenceFetcher:
    def fetch_latest_pubmed(self, query: str, max_results: int = 3) -> list:
        try:
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": max_results, "sort": "pub_date"}
            search_res = requests.get(search_url, params=search_params, timeout=10).json()
            id_list = search_res.get("esearchresult", {}).get("idlist", [])

            if not id_list:
                return [{"source": "PubMed", "id": "N/A", "text": "No recent articles found."}]

            summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            summary_params = {"db": "pubmed", "id": ",".join(id_list), "retmode": "json"}
            summary_res = requests.get(summary_url, params=summary_params, timeout=10).json()
            uid_results = summary_res.get("result", {})

            articles = []
            for uid in id_list:
                if uid in uid_results:
                    art = uid_results[uid]
                    articles.append({
                        "source": "PubMed",
                        "id": f"PMID_{uid}",
                        "text": f"Title: {art.get('title')} Published: {art.get('pubdate')}"
                    })
            return articles
        except Exception as e:
            return [{"source": "Error", "id": "Error", "text": str(e)}]

print("Loading BGE Reranker...")
reranker = CrossEncoder("BAAI/bge-reranker-base")
api_fetcher = LiveEvidenceFetcher()

def router_node(state: GraphState) -> dict:
    query = state["query"]
    prompt = f"Classify this query into 'Recency', 'Precision', 'Conceptual', or 'Both'. Query: {query}. Output ONLY the word."
    response = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt}])
    classification = response["message"]["content"].strip().lower()

    if "both" in classification: route = "both"
    elif "recency" in classification or "precision" in classification: route = "live_api"
    else: route = "static_vector"
        
    return {"route": route, "steps": state.get("steps", []) + [f"route_{route}"]}

def retrieve_node(state: GraphState) -> dict:
    route = state["route"]
    query = state["query"]
    merged_docs = []

    if route in ["live_api", "both"]:
        merged_docs.extend(api_fetcher.fetch_latest_pubmed(query, max_results=3))
    if route in ["static_vector", "both"]:
        local_docs = [
            {"source": "NCCN", "id": "NCCN_v3", "text": "Preferred first-line targeted therapies include osimertinib."},
            {"source": "NCCN", "id": "NCCN_v4", "text": "Sotorasib is indicated for KRAS G12C."}
        ]
        merged_docs.extend(local_docs)
    return {"documents": merged_docs, "steps": state["steps"] + ["retrieve"]}

def grade_evidence_node(state: GraphState) -> dict:
    query = state["query"]
    docs = state["documents"]
    if not docs or docs[0].get("id") == "Error":
        return {"route": "insufficient", "steps": state["steps"] + ["grade_failed"]}

    pairs = [[query, d["text"]] for d in docs]
    scores = reranker.predict(pairs)
    max_score = max(scores) if isinstance(scores, (list, tuple, type(scores))) else scores
    decision = "sufficient" if max_score > -2.0 else "insufficient"
    return {"route": decision, "steps": state["steps"] + [f"grade_{decision}"]}

def augment_node(state: GraphState) -> dict:
    return {"query": f"latest clinical trials for: {state['query']}", "route": "live_api", "steps": state["steps"] + ["augment"]}

# --- PHASE 7: GROUNDED GENERATION NODE ---
def generate_node(state: GraphState) -> dict:
    print("--- NODE: GENERATE ---")
    formatted_context = "\n".join([f"[{d['source']} {d['id']}] {d['text']}" for d in state["documents"]])

    system_prompt = """You are an expert Oncology Assistant.
Answer strictly using the provided context blocks.
CRITICAL INSTRUCTION: You MUST append the exact Source ID bracket to the end of every sentence containing a clinical claim. 
Example: "Targeted therapy has shown improved outcomes [PubMed PMID_123456]." """

    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"CONTEXT:\n{formatted_context}\n\nQUESTION: {state['query']}"},
        ],
    )
    return {"generation": response["message"]["content"], "steps": state["steps"] + ["generate"]}

def decider_after_grading(state: GraphState) -> Literal["generate", "augment"]:
    return "generate" if state["route"] == "sufficient" else "augment"

# --- COMPILE FULL GRAPH ---
workflow = StateGraph(GraphState)
workflow.add_node("router", router_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("grade_evidence", grade_evidence_node)
workflow.add_node("augment", augment_node)
workflow.add_node("generate", generate_node)

workflow.set_entry_point("router")
workflow.add_edge("router", "retrieve")
workflow.add_edge("retrieve", "grade_evidence")
workflow.add_conditional_edges("grade_evidence", decider_after_grading, {"generate": "generate", "augment": "augment"})
workflow.add_edge("augment", "retrieve")
workflow.add_edge("generate", END)

app = workflow.compile()

if __name__ == "__main__":
    test_query = "What are the recommended treatments for KRAS G12C and what does the latest literature say?"
    inputs = {"query": test_query}

    print("=======================================================")
    print(f"Executing End-to-End Citation Generator for: '{test_query}'")
    print("=======================================================\n")

    final_generation = ""
    final_steps = []

    for output in app.stream(inputs):
        for node_name, state_update in output.items():
            if "generation" in state_update:
                final_generation = state_update["generation"]
            if "steps" in state_update:
                final_steps = state_update["steps"]

    print("FINAL GENERATED CITED RESPONSE:\n")
    print(final_generation)
    print(f"\nExecution Path: {' -> '.join(final_steps)}")