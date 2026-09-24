"""Single-technique baselines for the pilot-study benchmark (paper Sec. VIII).

The hybrid cascade is compared against each of its stages run alone:
  * kg_only    — Stage 1 knowledge-graph eligibility ordering
  * cf_only    — Stage 2 FES-weighted item-to-item CF
  * fm_only    — Stage 3 Factorisation Machine scoring
  * popularity — non-personalised co-occurrence popularity fallback
"""


class SingleTechniqueBaseline:
    """Phase 9: wrap one technique as a full ranking pipeline for comparison."""

    def __init__(self, technique: str):
        if technique not in ("kg_only", "cf_only", "fm_only", "popularity"):
            raise ValueError(f"Unknown baseline: {technique}")
        self.technique = technique

    def rank(self, student: dict, candidate_items: list) -> list:
        raise NotImplementedError("Phase 9")
