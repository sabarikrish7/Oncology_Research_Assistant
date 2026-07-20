import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")

client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

count = client.count(collection_name="oncology_guidelines")
print(f"Total chunks in oncology_guidelines: {count.count}")
