import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from sentence_transformers import SentenceTransformer
from src.config import EMBEDDING_MODEL

# Load environment variables from the .env file
load_dotenv()

_ENCODER_INSTANCE = None

def get_encoder():
    global _ENCODER_INSTANCE
    if _ENCODER_INSTANCE is None:
        print(f"Loading embedding model ({EMBEDDING_MODEL})...")
        _ENCODER_INSTANCE = SentenceTransformer(EMBEDDING_MODEL)
    return _ENCODER_INSTANCE


class HybridRetriever:
    """Phase 2 & 3: Qdrant Cloud Vector Database and Semantic Retrieval Engine."""

    def __init__(self, collection_name: str = "oncology_guidelines"):
        self.collection_name = collection_name

        # Pull secure credentials from the environment
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if not qdrant_url or not qdrant_api_key:
            raise ValueError(
                "Missing Qdrant Cloud credentials! Please check your .env file."
            )

        # Connect directly to the Qdrant Cloud cluster
        self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

        self.encoder = get_encoder()
        self._ensure_collection()

    def _ensure_collection(self):
        """Creates the collection if it does not already exist."""
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.encoder.get_embedding_dimension(),
                    distance=Distance.COSINE,
                ),
            )
            print(
                f"Qdrant collection '{self.collection_name}' initialized on Qdrant Cloud."
            )

    def index_documents(self, documents: List[Dict[str, Any]]):
        """Encodes and indexes parsed chunks into the Cloud."""
        if not documents:
            return

        points = []
        texts = [doc.get("text", "") for doc in documents]
        embeddings = self.encoder.encode(texts, show_progress_bar=True)

        for idx, (doc, emb) in enumerate(zip(documents, embeddings)):
            points.append(PointStruct(id=idx, vector=emb.tolist(), payload=doc))

        self.client.upsert(collection_name=self.collection_name, points=points)
        print(f"Successfully indexed {len(points)} chunks into Qdrant Cloud.")

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Executes a semantic vector search and formats output for LangGraph."""
        query_vector = self.encoder.encode(query).tolist()

        search_result = self.client.query_points(
            collection_name=self.collection_name, query=query_vector, limit=limit
        ).points

        formatted_results = []
        for hit in search_result:
            payload = hit.payload or {}
            metadata = payload.get("metadata", {})
            publisher = metadata.get("publisher", "LocalDB")

            formatted_results.append(
                {
                    "source": publisher,
                    "id": metadata.get("chunk_id", f"ID_{hit.id}")[:8],
                    "text": payload.get("text", ""),
                }
            )

        return formatted_results
