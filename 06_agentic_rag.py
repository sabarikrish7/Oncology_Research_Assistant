import json
import requests
import ollama
from typing import List, Literal, TypedDict
from sentence_transformers import CrossEncoder
from langgraph.graph import StateGraph, END


# Define the schema for our graph state
class GraphState(TypedDict):
    query: str
    route: str
    documents: List[dict]  # Upgraded to hold dictionaries with text and sources
    generation: str
    steps: List[str]
    retries: int


class LiveEvidenceFetcher:
    """Phase 5 Component: Fetches real-time data."""

    def fetch_latest_pubmed(self, query: str, max_results: int = 3) -> list:
        try:
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": max_results,
                "sort": "pub_date",
            }
            search_res = requests.get(
                search_url, params=search_params, timeout=10
            ).json()
            id_list = search_res.get("esearchresult", {}).get("idlist", [])

            if not id_list:
                return [
                    {
                        "source": "PubMed",
                        "text": "No recent articles found.",
                        "id": "N/A",
                    }
                ]

            summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            summary_params = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json",
            }
            summary_res = requests.get(
                summary_url, params=summary_params, timeout=10
            ).json()
            uid_results = summary_res.get("result", {})

            articles = []
            for uid in id_list:
                if uid in uid_results:
                    art = uid_results[uid]
                    articles.append(
                        {
                            "source": "PubMed",
                            "id": f"PMID_{uid}",
                            "text": f"Title: {art.get('title')} Published: {art.get('pubdate')}",
                        }
                    )
            return articles
        except Exception as e:
            return [{"source": "Error", "text": str(e), "id": "Error"}]


# Load the CrossEncoder once globally to save time during loops
print("Loading BGE Reranker...")
reranker = CrossEncoder("BAAI/bge-reranker-base")
api_fetcher = LiveEvidenceFetcher()


def router_node(state: GraphState) -> dict:
    """Phase 3 Component: Agentic Routing via Llama 3."""
    print("--- NODE: ROUTER ---")
    query = state["query"]

    prompt = f"Classify this query into 'Recency', 'Precision', or 'Conceptual'. Query: {query}. Output ONLY the word."
    response = ollama.chat(
        model="llama3", messages=[{"role": "user", "content": prompt}]
    )
    classification = response["message"]["content"].strip().lower()

    route = (
        "live_api"
        if "recency" in classification or "precision" in classification
        else "static_vector"
    )
    return {"route": route, "steps": state.get("steps", []) + [f"route_{route}"]}


def retrieve_node(state: GraphState) -> dict:
    """Phase 3/5 Component: Retrieves from Live APIs or Static Vectors."""
    print("--- NODE: RETRIEVE ---")
    route = state["route"]
    query = state["query"]

    if route == "live_api":
        print("  -> Fetching live data from PubMed...")
        docs = api_fetcher.fetch_latest_pubmed(query, max_results=3)
    else:
        print("  -> Fetching from Static Qdrant DB (Simulated)...")
        docs = [
            {
                "source": "NCCN",
                "id": "NCCN_v3",
                "text": "Preferred first-line targeted therapies include osimertinib.",
            },
            {
                "source": "NCCN",
                "id": "NCCN_v4",
                "text": "Sotorasib is indicated for KRAS G12C.",
            },
        ]

    return {"documents": docs, "steps": state["steps"] + ["retrieve"]}


def grade_evidence_node(state: GraphState) -> dict:
    """Phase 4 Component: Grades documents using BGE Reranker."""
    print("--- NODE: GRADE EVIDENCE ---")
    query = state["query"]
    docs = state["documents"]

    if not docs or docs[0].get("id") == "Error":
        return {"route": "insufficient", "steps": state["steps"] + ["grade_failed"]}

    # Prepare pairs for cross-encoder scoring
    pairs = [[query, d["text"]] for d in docs]
    scores = reranker.predict(pairs)

    # Check if the highest score passes our relevance threshold
    # BGE reranker outputs logits, generally > 0 implies relevance.
    max_score = (
        max(scores) if isinstance(scores, (list, tuple, type(scores))) else scores
    )
    print(f"  -> Top Reranker Score: {max_score:.2f}")

    decision = "sufficient" if max_score > -2.0 else "insufficient"
    return {"route": decision, "steps": state["steps"] + [f"grade_{decision}"]}


def augment_node(state: GraphState) -> dict:
    """Rewrites the query if evidence is weak."""
    print("--- NODE: AUGMENT ---")
    return {
        "query": f"latest clinical trials and results for: {state['query']}",
        "route": "live_api",
        "steps": state["steps"] + ["augment"],
    }


def generate_node(state: GraphState) -> dict:
    """Phase 6/7 Component: Generates citation-grounded response."""
    print("--- NODE: GENERATE ---")

    # Format context with explicit Source IDs
    formatted_context = "\n".join(
        [f"[{d['source']} {d['id']}] {d['text']}" for d in state["documents"]]
    )

    system_prompt = """You are an expert Oncology Assistant.
Answer strictly using the provided context.
CRITICAL: You MUST append the exact Source ID bracket to your claims. 
Example: "Sotorasib is effective [PubMed PMID_12345]." """

    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"CONTEXT:\n{formatted_context}\n\nQUESTION: {state['query']}",
            },
        ],
    )

    return {
        "generation": response["message"]["content"],
        "steps": state["steps"] + ["generate"],
    }


def validate_node(state: GraphState) -> dict:
    """Checks for hallucinated formatting."""
    print("--- NODE: VALIDATE ---")
    generation = state["generation"]

    # Check if brackets exist in the response
    if "[" not in generation or "]" not in generation:
        print("  -> Guardrail Alert: Missing Citations! Retrying...")
        verdict = "fail"
    else:
        print("  -> Guardrail Passed: Citations Found.")
        verdict = "pass"

    return {
        "route": verdict,
        "steps": state["steps"] + ["validate"],
        "retries": state.get("retries", 0) + 1,
    }


def decider_after_grading(state: GraphState) -> Literal["generate", "augment"]:
    return "generate" if state["route"] == "sufficient" else "augment"


def decider_after_validation(state: GraphState) -> Literal["respond", "generate"]:
    if state["route"] == "pass" or state.get("retries", 0) >= 2:
        return "respond"
    return "generate"


workflow = StateGraph(GraphState)
workflow.add_node("router", router_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("grade_evidence", grade_evidence_node)
workflow.add_node("augment", augment_node)
workflow.add_node("generate", generate_node)
workflow.add_node("validate", validate_node)

workflow.set_entry_point("router")
workflow.add_edge("router", "retrieve")
workflow.add_edge("retrieve", "grade_evidence")
workflow.add_conditional_edges(
    "grade_evidence",
    decider_after_grading,
    {"generate": "generate", "augment": "augment"},
)
workflow.add_edge("augment", "retrieve")
workflow.add_edge("generate", "validate")
workflow.add_conditional_edges(
    "validate", decider_after_validation, {"respond": END, "generate": "generate"}
)

app = workflow.compile()

if __name__ == "__main__":
    test_query = "What are the newest treatments for KRAS G12C in lung cancer?"
    inputs = {"query": test_query, "retries": 0}

    print("\n=======================================================")
    print(f"Executing Integrated Pipeline for: '{test_query}'")
    print("=======================================================\n")

    # We need a variable to hold the full state across the stream
    final_generation = ""
    final_steps = []

    for output in app.stream(inputs):
        # output is a dict like {'generate': {'generation': '...', 'steps': [...]}}
        for node_name, state_update in output.items():
            if "generation" in state_update:
                final_generation = state_update["generation"]
            if "steps" in state_update:
                final_steps = state_update["steps"]

    print("\n=======================================================")
    print("FINAL GENERATED RESPONSE:")
    print("=======================================================\n")
    print(final_generation)
    print(f"\nExecution Path: {' -> '.join(final_steps)}")

