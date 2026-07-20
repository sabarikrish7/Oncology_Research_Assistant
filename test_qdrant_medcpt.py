import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()
client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))

# count documents in medcpt
count = client.count(collection_name="oncology_guidelines_medcpt")
print(f"MedCPT Collection count: {count.count}")

# look at one document
res = client.scroll(collection_name="oncology_guidelines_medcpt", limit=1)
if res[0]:
    print("Example doc payload:", res[0][0].payload.keys())
    print("Example doc id:", res[0][0].id)
    if "metadata" in res[0][0].payload:
        print("Metadata chunk_id:", res[0][0].payload["metadata"].get("chunk_id"))
