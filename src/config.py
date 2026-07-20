import os

# Configuration file for Oncology Research Assistant

# Model Configurations
OLLAMA_MODEL = "llama3"
QUERY_EMBEDDING_MODEL = "ncbi/MedCPT-Query-Encoder"
DOC_EMBEDDING_MODEL = "ncbi/MedCPT-Article-Encoder"
RERANKER_MODEL = "BAAI/bge-reranker-base"

if "MedCPT" in QUERY_EMBEDDING_MODEL:
    COLLECTION_NAME = "oncology_guidelines_medcpt"
else:
    COLLECTION_NAME = "oncology_guidelines"

# Retrieval & Routing Settings
MAX_RETRIES = 2
PUBMED_MAX_RESULTS = 8
CLINICAL_TRIALS_MAX_RESULTS = 5
STATIC_RETRIEVAL_LIMIT = 15
RERANKED_TOP_K = 6

# APIs
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "f8e7805dd48fd452bd183dc9f2af66c41108")

# Ingestion Settings
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

# Validation Settings
RERANK_BASE_MULTIPLIER = 4
RERANK_BASE_OFFSET = 5
RERANK_BASE_MAX = 20.0
