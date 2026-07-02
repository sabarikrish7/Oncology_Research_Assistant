import os
import json
from typing import List, Literal, TypedDict
import ollama
from langgraph.graph import StateGraph, END

from src.live_apis import LiveEvidenceFetcher
from src.retrieval import HybridRetriever
from src.reranking import ClinicalReranker
from src.validation import NumericValidator, EvidenceVerifier, ConfidenceScorer
from src.config import MAX_RETRIES, OLLAMA_MODEL, STATIC_RETRIEVAL_LIMIT, PUBMED_MAX_RESULTS, CLINICAL_TRIALS_MAX_RESULTS

class GraphState(TypedDict):
    query: str
    route: str
    documents: List[dict]
    generation: str
    steps: List[str]
    retries: int
    validation_report: dict

api_fetcher = LiveEvidenceFetcher()
static_retriever = HybridRetriever()
clinical_reranker = ClinicalReranker()

def router_node(state: GraphState) -> dict:
    query = state["query"]
    prompt = f"Classify this query into 'Recency' (PubMed), 'Trials' (ClinicalTrials), 'Conceptual' (Guidelines), or 'All'. Query: {query}. Output ONLY a JSON object with a single key 'route' containing one of these four words."
    response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}], format="json")
    try:
        classification = json.loads(response["message"]["content"].strip())
        route_val = classification.get("route", "conceptual").lower()
    except json.JSONDecodeError:
        route_val = "conceptual"

    if "all" in route_val: route = "all"
    elif "trial" in route_val: route = "trials"
    elif "recency" in route_val: route = "recency"
    else: route = "conceptual"
    
    return {"route": route, "steps": state.get("steps", []) + [f"route_{route}"]}

def retrieve_node(state: GraphState) -> dict:
    route = state["route"]
    query = state["query"]
    merged_docs = []

    if route in ["recency", "all"]:
        merged_docs.extend(api_fetcher.fetch_latest_pubmed(query, max_results=PUBMED_MAX_RESULTS))
    if route in ["trials", "all"] or "NCT" in query.upper():
        merged_docs.extend(api_fetcher.fetch_clinical_trial(query, max_results=CLINICAL_TRIALS_MAX_RESULTS))
    if route in ["conceptual", "all"]:
        merged_docs.extend(static_retriever.search(query, limit=STATIC_RETRIEVAL_LIMIT))

    return {"documents": merged_docs, "steps": state["steps"] + ["retrieve"]}

def grade_evidence_node(state: GraphState) -> dict:
    query = state["query"]
    docs = state["documents"]
    if not docs:
        return {"route": "insufficient", "steps": state["steps"] + ["grade_failed"]}

    scored_docs, max_score = clinical_reranker.rerank(query, docs)
    decision = "sufficient" if max_score > 1.0 else "insufficient"
    return {"route": decision, "documents": scored_docs, "steps": state["steps"] + [f"grade_{decision}"]}

def augment_node(state: GraphState) -> dict:
    prompt = f"Extract only the core medical condition, drug, or biomarker from this query to use as a search term for PubMed and ClinicalTrials.gov. Return ONLY the search term, no extra words or punctuation. Query: {state['query']}"
    response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
    clean_query = response["message"]["content"].strip().strip('"\'')
    return {"query": clean_query, "route": "all", "steps": state["steps"] + ["augment"]}

def generate_node(state: GraphState) -> dict:
    formatted_context = "\n".join([f"[{d['source']} {d['id']}] {d['text']}" for d in state["documents"]])
    system_prompt = """You are an expert Oncology AI Assistant. 
Answer the question strictly using the provided context blocks. 
For EVERY claim or metric you extract, you MUST append the exact Source ID bracket to the end of the sentence.
Example text: 'Sotorasib demonstrated a prolonged progression-free survival rate [PubMed PMID_356535].'"""

    response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"CONTEXT:\n{formatted_context}\n\nQUESTION: {state['query']}"}])
    return {"generation": response["message"]["content"], "steps": state["steps"] + ["generate"]}

def validate_node(state: GraphState) -> dict:
    generation = state["generation"]
    docs = state["documents"]
    numeric_report = NumericValidator.validate(generation, docs)
    llm_report = EvidenceVerifier.verify(generation, docs)
    composite = ConfidenceScorer.calculate(numeric_report, llm_report, docs)
    verdict = "pass" if composite["is_safe_to_display"] else "fail"
    return {"route": verdict, "validation_report": composite, "steps": state["steps"] + [f"validate_{verdict}"], "retries": state.get("retries", 0) + 1}

def decider_after_grading(state: GraphState) -> Literal["generate", "augment"]:
    # Hard stop to prevent infinite augment loops
    if "augment" in state.get("steps", []):
        return "generate"
    return "generate" if state["route"] == "sufficient" else "augment"

def decider_after_validation(state: GraphState) -> Literal["respond", "generate"]:
    if state["route"] == "pass" or state.get("retries", 0) >= MAX_RETRIES: return "respond"
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
workflow.add_conditional_edges("grade_evidence", decider_after_grading, {"generate": "generate", "augment": "augment"})
workflow.add_edge("augment", "retrieve")
workflow.add_edge("generate", "validate")
workflow.add_conditional_edges("validate", decider_after_validation, {"respond": END, "generate": "generate"})

oncology_rag_agent = workflow.compile()