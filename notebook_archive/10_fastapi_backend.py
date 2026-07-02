import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

# Initialize the FastAPI application with metadata for the Swagger UI
app = FastAPI(
    title="Oncology Agentic RAG API",
    description="Backend service for retrieving, generating, and validating clinical oncology evidence.",
    version="1.0.0",
)

# --- SCHEMAS ---


class SearchRequest(BaseModel):
    query: str = Field(..., example="What is the targeted therapy for KRAS G12C?")
    use_live_api: bool = Field(
        default=True, description="Toggle between live API and static vectors."
    )


class SearchResponse(BaseModel):
    query: str
    answer: str
    confidence_score: str
    references: List[str]


class ValidateRequest(BaseModel):
    claim: str = Field(..., example="Sotorasib has a 99.9% response rate.")
    context: str = Field(..., example="The objective response rate was 37.1%.")


class ValidateResponse(BaseModel):
    status: str
    reasoning: str
    is_safe_to_display: bool


# --- MOCK DATABASE ---
# Simulates the Qdrant database you built in Phase 2
MOCK_SOURCES_DB = {
    "NCCN_v3": {
        "title": "NCCN Guidelines - Non-Small Cell Lung Cancer",
        "text": "Preferred first-line targeted therapies include osimertinib for EGFR mutations.",
        "year": "2023",
    },
    "PMID_111": {
        "title": "Sotorasib in KRAS G12C-Mutated Advanced Solid Tumors",
        "text": "Sotorasib showed a 37.1% objective response rate in the phase 2 trial.",
        "year": "2026",
    },
}

# --- ENDPOINTS ---


@app.get("/health", tags=["System"])
async def health_check():
    """Returns the operational status of the API."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "message": "Oncology API is active.",
    }


@app.post("/search", response_model=SearchResponse, tags=["RAG Pipeline"])
async def search_oncology_evidence(request: SearchRequest):
    """
    Executes Phase 6/7 workflow: Routes query, retrieves evidence, and generates grounded answer.
    """
    # Simulated execution of your LangGraph + Llama 3 Pipeline
    print(f"--> [ROUTER] Received query: '{request.query}'")

    # Mocking the Phase 7 Generator Output
    return SearchResponse(
        query=request.query,
        answer="Sotorasib is indicated for advanced NSCLC with KRAS G12C mutations [PMID_111].",
        confidence_score="High (100%) - Strongly Grounded",
        references=[
            "[PMID_111] PubMed: Sotorasib in KRAS G12C-Mutated Advanced Solid Tumors"
        ],
    )


@app.post("/validate", response_model=ValidateResponse, tags=["Guardrails"])
async def validate_claim(request: ValidateRequest):
    """
    Executes Phase 8 workflow: Checks generated claims against source context for hallucinations.
    """
    print("--> [VALIDATOR] Running numeric and LLM verification...")

    # Simulating your Phase 8 Confidence Scorer logic
    if "99.9" in request.claim:
        return ValidateResponse(
            status="UNSUPPORTED",
            reasoning="The claim of 99.9% significantly exaggerates the source text's 37.1%.",
            is_safe_to_display=False,
        )

    return ValidateResponse(
        status="SUPPORTED",
        reasoning="The generated claim matches the numerical data reported in the source evidence.",
        is_safe_to_display=True,
    )


@app.get("/sources/{source_id}", tags=["Retrieval"])
async def get_source_document(source_id: str):
    """
    Retrieves the raw text and metadata of a specific document chunk by its ID.
    """
    document = MOCK_SOURCES_DB.get(source_id)
    if not document:
        raise HTTPException(
            status_code=404, detail=f"Source ID '{source_id}' not found in database."
        )

    return {"source_id": source_id, "document": document}


# --- EXECUTION ---
if __name__ == "__main__":
    print("\n=======================================================")
    print("STARTING FASTAPI SERVER FOR ONCOLOGY RAG")
    print("Interactive Swagger UI available at: http://localhost:8000/docs")
    print("=======================================================\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
