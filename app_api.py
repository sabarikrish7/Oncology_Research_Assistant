import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from src.engine import oncology_rag_agent

app = FastAPI(
    title="🧬 Multi-Source Oncology RAG Engine",
    version="2.1.0",
    description="FastAPI layer merging Qdrant Server, PubMed, ClinicalTrials.gov, and Llama 3.",
)

class SearchQuery(BaseModel):
    query: str

class SearchResponse(BaseModel):
    query: str
    generation: str
    execution_path: str
    validation_metrics: Dict[str, Any]
    retrieved_sources: List[Dict[str, Any]]

@app.get("/health")
def health_check():
    return {"status": "healthy", "engine": "LangGraph Orchestrator Active"}

@app.post("/search", response_model=SearchResponse)
def execute_agentic_search(payload: SearchQuery):
    try:
        inputs = {"query": payload.query, "retries": 0}
        final_generation = ""
        final_steps = []
        final_report = {}
        final_docs = []

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

        if final_report and not final_report.get("is_safe_to_display", False):
            final_generation = "⚠️ [CLINICAL GUARDRAIL BLOCK]: The generated response failed strict validation checks. Please review source context explicitly below."

        return {
            "query": payload.query, 
            "generation": final_generation if final_generation else "Failed to produce a valid response context loop.", 
            "execution_path": " ➔ ".join(final_steps), 
            "validation_metrics": final_report, 
            "retrieved_sources": final_docs
        }

    except Exception as e:
        import traceback
        print("\n🚨 BACKEND CRASH DETECTED 🚨")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_api:app", host="0.0.0.0", port=8000, reload=False)