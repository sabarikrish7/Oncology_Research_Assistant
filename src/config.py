# Configuration file for Oncology Research Assistant

# Model Configurations
OLLAMA_MODEL = "llama3"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL = "BAAI/bge-reranker-base"

# Retrieval & Routing Settings
MAX_RETRIES = 2
PUBMED_MAX_RESULTS = 2
CLINICAL_TRIALS_MAX_RESULTS = 2
STATIC_RETRIEVAL_LIMIT = 4

# Ingestion Settings
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

# Validation Settings
RERANK_BASE_MULTIPLIER = 4
RERANK_BASE_OFFSET = 5
RERANK_BASE_MAX = 20.0
