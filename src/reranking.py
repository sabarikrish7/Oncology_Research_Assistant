from typing import List, Dict, Any, Tuple
from sentence_transformers import CrossEncoder
from src.config import RERANKER_MODEL

_RERANKER_INSTANCE = None

def get_reranker():
    global _RERANKER_INSTANCE
    if _RERANKER_INSTANCE is None:
        print(f"Loading Cross-Encoder Reranker (on CPU): {RERANKER_MODEL}...")
        _RERANKER_INSTANCE = CrossEncoder(RERANKER_MODEL, device="cpu")
    return _RERANKER_INSTANCE


class ClinicalReranker:
    """Phase 4: Cross-Encoder Reranker for Evidence Grading."""

    def __init__(self):
        self.reranker = get_reranker()

    def rerank(
        self, query: str, documents: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], float]:
        if not documents:
            return [], -99.0

        pairs = [[query, doc.get("text", "")] for doc in documents]
        scores = self.reranker.predict(pairs)

        if isinstance(scores, (float, int)):
            scores = [float(scores)]
        else:
            scores = scores.tolist()

        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)

        ranked_docs = sorted(documents, key=lambda x: x["rerank_score"], reverse=True)
        max_score = ranked_docs[0]["rerank_score"]

        return ranked_docs, max_score
