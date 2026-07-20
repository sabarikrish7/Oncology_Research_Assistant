import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from src.config import QUERY_EMBEDDING_MODEL, DOC_EMBEDDING_MODEL, COLLECTION_NAME

# Load environment variables from the .env file
load_dotenv()

_QUERY_ENCODER = None
_DOC_ENCODER = None

def get_query_encoder():
    global _QUERY_ENCODER
    if _QUERY_ENCODER is None:
        print(f"Loading query embedding model ({QUERY_EMBEDDING_MODEL})...")
        _QUERY_ENCODER = SentenceTransformer(QUERY_EMBEDDING_MODEL, device="cuda")
    return _QUERY_ENCODER

def get_doc_encoder():
    global _DOC_ENCODER
    if _DOC_ENCODER is None:
        print(f"Loading document embedding model ({DOC_EMBEDDING_MODEL})...")
        _DOC_ENCODER = SentenceTransformer(DOC_EMBEDDING_MODEL, device="cuda")
    return _DOC_ENCODER


class HybridRetriever:
    """Phase 2 & 3: Qdrant Cloud Vector Database and Semantic Retrieval Engine."""

    def __init__(self, collection_name: str = COLLECTION_NAME):
        self.collection_name = collection_name

        # Pull secure credentials from the environment
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if not qdrant_url or not qdrant_api_key:
            raise ValueError(
                "Missing Qdrant Cloud credentials! Please check your .env file."
            )

        # Connect directly to the Qdrant Cloud cluster
        self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=120.0)

        self.query_encoder = get_query_encoder()
        self.doc_encoder = get_doc_encoder()
        self._ensure_collection()
        self._initialize_bm25()

    def _initialize_bm25(self):
        """Scrolls through the entire Qdrant collection to build an in-memory BM25 index."""
        print("Building BM25 index from Qdrant Cloud...")
        self.bm25_corpus = []
        self.bm25_payloads = []
        
        if not self.client.collection_exists(self.collection_name):
            self.bm25 = None
            return

        next_page_offset = None
        while True:
            records, next_page_offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=100,
                with_payload=True,
                with_vectors=False,
                offset=next_page_offset
            )
            for record in records:
                payload = record.payload or {}
                text = payload.get("text", "")
                self.bm25_corpus.append(text.lower().split())
                self.bm25_payloads.append({
                    "id": record.id,
                    "payload": payload
                })
                
            if next_page_offset is None:
                break
                
        if self.bm25_corpus:
            self.bm25 = BM25Okapi(self.bm25_corpus)
            print(f"BM25 index built with {len(self.bm25_corpus)} documents.")
        else:
            self.bm25 = None

    def _ensure_collection(self):
        """Creates the collection if it does not already exist."""
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.doc_encoder.get_embedding_dimension(),
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
        embeddings = self.doc_encoder.encode(texts, show_progress_bar=True)

        for doc, emb in zip(documents, embeddings):
            chunk_id = doc.get("metadata", {}).get("chunk_id")
            points.append(PointStruct(id=chunk_id, vector=emb.tolist(), payload=doc))

        self.client.upsert(collection_name=self.collection_name, points=points)
        print(f"Successfully indexed {len(points)} chunks into Qdrant Cloud.")

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Executes a semantic vector search and formats output for LangGraph."""
        query_vector = self.query_encoder.encode(query).tolist()

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

    def hybrid_search(self, query: str, limit: int = 5, rrf_k: int = 60) -> List[Dict[str, Any]]:
        """Executes a hybrid search merging semantic and BM25 results via RRF."""
        semantic_results = self.search(query, limit=limit)
        
        bm25_results = []
        if getattr(self, 'bm25', None) is not None:
            tokenized_query = query.lower().split()
            scores = self.bm25.get_scores(tokenized_query)
            
            top_n = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:limit]
            
            for rank, idx in enumerate(top_n):
                if scores[idx] > 0:
                    payload = self.bm25_payloads[idx]["payload"]
                    metadata = payload.get("metadata", {})
                    publisher = metadata.get("publisher", "LocalDB")
                    hit_id = self.bm25_payloads[idx]["id"]
                    
                    bm25_results.append({
                        "source": publisher,
                        "id": metadata.get("chunk_id", f"ID_{hit_id}")[:8],
                        "text": payload.get("text", ""),
                    })
        
        rrf_scores = {}
        doc_map = {}
        
        for rank, doc in enumerate(semantic_results):
            doc_id = doc["id"]
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
                doc_map[doc_id] = doc
            rrf_scores[doc_id] += 1.0 / (rrf_k + rank + 1)
            
        for rank, doc in enumerate(bm25_results):
            doc_id = doc["id"]
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
                doc_map[doc_id] = doc
            rrf_scores[doc_id] += 1.0 / (rrf_k + rank + 1)
            
        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        fused_results = []
        for doc_id, score in sorted_docs[:limit]:
            doc = doc_map[doc_id].copy()
            doc["rrf_score"] = score
            fused_results.append(doc)
            
        return fused_results
