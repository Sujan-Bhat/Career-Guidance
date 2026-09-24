"""Plain-language recommendation explanations (NFR07, Phase 7).

Input: a recommendation with per-stage cascade provenance + contributing
profile features (including FES). Output: a short, non-technical explanation
of WHY the item was recommended to THIS student.
"""


def generate_explanation(recommendation: dict, contributing_features: list[dict]) -> str:
    """Phase 7: prompt the LLM with the recommendation's Stage 1-3 provenance
    (KG eligibility, CF affinity, FM score) and top features; return the
    explanation string to store on the Recommendation document."""
    raise NotImplementedError("Phase 7")
