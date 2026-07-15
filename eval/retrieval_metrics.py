import math
from typing import List

def calculate_hit_rate(expected_id: str, retrieved_ids: List[str], k: int = 5) -> int:
    """Returns 1 if expected_id is in top k, else 0."""
    return 1 if expected_id in retrieved_ids[:k] else 0

def calculate_mrr(expected_id: str, retrieved_ids: List[str]) -> float:
    """Calculates Mean Reciprocal Rank for a single query."""
    try:
        rank = retrieved_ids.index(expected_id) + 1
        return 1.0 / rank
    except ValueError:
        return 0.0

def calculate_ndcg(expected_id: str, retrieved_ids: List[str], k: int = 5) -> float:
    """Calculates nDCG@K assuming binary relevance (1 for exact chunk)."""
    if expected_id in retrieved_ids[:k]:
        rank = retrieved_ids.index(expected_id) + 1
        # IDCG = 1 since there is only 1 relevant document
        return 1.0 / math.log2(rank + 1)
    return 0.0
