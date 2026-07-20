from qdrant_client import QdrantClient
from src.config import COLLECTION_NAME

client = QdrantClient(url="https://264d3600-f623-4560-93a5-ee7d130f146a.us-east4-0.gcp.cloud.qdrant.io:6333", api_key="d78b8849646be149c47e834b17bc6cb312dd013c7bc37fb51656a8fb9cf60a37")

records = client.scroll(
    collection_name=COLLECTION_NAME,
    limit=5
)[0]

for r in records:
    print(r.id)
    print(r.payload.get("metadata", {}).get("chunk_id"))
    break
