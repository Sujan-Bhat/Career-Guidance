"""Stage 2: collaborative re-ranking (paper Sec. V-B).

Item-to-item collaborative filtering [32] over course/pathway co-occurrence,
using the implicit-feedback framework of Koren et al. [2]: each session's
contribution to the CF score is weighted by its FES value, so higher-focus
sessions carry more influence.
"""


def item_cooccurrence(session_items: list, fes_weights: list) -> dict:
    """Build FES-weighted item-to-item co-occurrence counts."""
    raise NotImplementedError("Phase 4")


def cf_rerank(candidates: list, cooccurrence: dict, student_history: list) -> list:
    """Re-rank Stage-1 candidates by FES-weighted CF affinity."""
    raise NotImplementedError("Phase 4")
