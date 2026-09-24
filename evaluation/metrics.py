"""Ranking metrics for the pilot study (paper Sec. VIII).

Used to benchmark the 3-stage cascade against single-technique baselines
(KG-only, CF-only, FM-only).
"""
import math


def precision_at_k(recommended: list, relevant: set, k: int = 10) -> float:
    """Fraction of the top-k recommended items that are relevant."""
    if k <= 0:
        raise ValueError("k must be positive")
    top_k = recommended[:k]
    return sum(1 for item in top_k if item in relevant) / k


def recall_at_k(recommended: list, relevant: set, k: int = 10) -> float:
    """Fraction of relevant items recovered in the top-k."""
    if not relevant:
        return 0.0
    top_k = recommended[:k]
    return sum(1 for item in top_k if item in relevant) / len(relevant)


def ndcg_at_k(recommended: list, relevant: set, k: int = 10) -> float:
    """Normalised discounted cumulative gain at k (binary relevance)."""
    dcg = sum(1.0 / math.log2(i + 2) for i, item in enumerate(recommended[:k]) if item in relevant)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal if ideal > 0 else 0.0
