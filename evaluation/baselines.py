"""Single-technique baselines for the pilot-study benchmark (paper Sec. VIII).

The hybrid cascade is compared against each of its stages run alone:
  * kg_only    — Stage 1 knowledge-graph eligibility ordering
  * cf_only    — Stage 2 FES-weighted item-to-item CF
  * fm_only    — Stage 3 Factorisation Machine scoring
  * popularity — non-personalised co-occurrence popularity fallback
"""
import numpy as np

from careermind_ml.recommender.cf import cf_score, _interaction_weight
from careermind_ml.recommender.features import vectorize
from careermind_ml.recommender.knowledge_graph import generate_candidates

TECHNIQUES = ("kg_only", "cf_only", "fm_only", "popularity")


class SingleTechniqueBaseline:
    """Wrap one technique as a full ranking pipeline for comparison.

    Context (constructor) carries whatever the technique needs:
      graph          — knowledge graph (kg_only)
      cooc           — FES-weighted item-item co-occurrence (cf_only)
      fm_model/spec  — trained FM artifact (fm_only)
      interactions/fes_by_session — for popularity counts
    `rank(student, candidate_items)` returns a FULL ordering of the
    candidate item ids (best first), so P@k/R@k/nDCG@k are comparable
    with the cascade's top-k output.
    """

    def __init__(
        self,
        technique: str,
        *,
        graph=None,
        cooc: dict | None = None,
        fm_model=None,
        fm_spec=None,
        interactions: list[dict] | None = None,
        fes_by_session: dict | None = None,
    ):
        if technique not in TECHNIQUES:
            raise ValueError(f"Unknown baseline: {technique}. Expected one of {TECHNIQUES}")
        if technique == "kg_only" and graph is None:
            raise ValueError("kg_only requires the knowledge graph")
        if technique == "cf_only" and cooc is None:
            raise ValueError("cf_only requires the co-occurrence matrix")
        if technique == "fm_only" and (fm_model is None or fm_spec is None):
            raise ValueError("fm_only requires the trained FM model and spec")
        self.technique = technique
        self.graph = graph
        self.cooc = cooc or {}
        self.fm_model = fm_model
        self.fm_spec = fm_spec
        self._popularity = self._build_popularity(interactions or [], fes_by_session or {})

    def _build_popularity(self, interactions: list[dict], fes_by_session: dict) -> dict:
        popularity: dict[str, float] = {}
        for interaction in interactions:
            item = interaction.get("item_id")
            if item:
                popularity[item] = popularity.get(item, 0.0) + _interaction_weight(interaction, fes_by_session)
        return popularity

    def rank(self, student: dict, candidate_items: list) -> list:
        """Order candidate item ids best-first for one student.

        `student`: {"skills": {skill: level}|None, "agg": features dict,
        "history": [item ids]} — same inputs the cascade consumes.
        """
        ids = [c if isinstance(c, str) else c["id"] for c in candidate_items]

        if self.technique == "kg_only":
            # eligibility for EVERY candidate (threshold 0 => full ordering);
            # generate_candidates already sorts by eligibility desc, id asc
            candidates = generate_candidates(student.get("skills") or {}, self.graph, threshold=0.0)
            wanted = set(ids)
            order = [c["id"] for c in candidates if c["id"] in wanted]
            return order + [i for i in sorted(ids) if i not in set(order)]

        if self.technique == "cf_only":
            history = student.get("history") or []
            scores = {i: cf_score(i, self.cooc, history) for i in ids}
            return sorted(ids, key=lambda i: (-scores[i], i))

        if self.technique == "fm_only":
            agg = student.get("agg") or {}
            scores = {}
            import torch

            for item in ids:
                x = vectorize(agg, item, self.fm_spec)
                with torch.no_grad():
                    scores[item] = float(self.fm_model(torch.as_tensor(x).unsqueeze(0)).item())
            return sorted(ids, key=lambda i: (-scores[i], i))

        # popularity: FES-weighted frequency, ties by id (non-personalised)
        return sorted(ids, key=lambda i: (-(self._popularity.get(i, 0.0)), i))


def popularity_ranking(interactions: list[dict], candidate_items: list, fes_by_session: dict | None = None) -> list:
    """Convenience: plain popularity ordering without constructing a baseline."""
    return SingleTechniqueBaseline(
        "popularity", interactions=interactions, fes_by_session=fes_by_session
    ).rank({}, candidate_items)
