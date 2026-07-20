from src.retrieval import HybridRetriever
from src.config import COLLECTION_NAME

retriever = HybridRetriever()
results = retriever.search("What is the diagnostic yield of limited BRCA1/2 analysis", limit=3)
for r in results:
    print(r)
