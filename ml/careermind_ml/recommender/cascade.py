"""Cascade orchestrator (paper Sec. V-B; Burke's [3] cascade hybrid pattern).

Stage 1: knowledge-graph candidate generation (>= 60% prerequisites)
Stage 2: FES-weighted item-to-item CF re-ranking
Stage 3: FES-augmented FM final scoring

Returns ranked recommendations WITH per-stage provenance so the LLM
explanation layer (NFR07) can cite why each item ranked.
"""


class CascadeRecommender:
    def __init__(self, knowledge_graph, cf_model, fm_model, config: dict):
        self.knowledge_graph = knowledge_graph
        self.cf_model = cf_model
        self.fm_model = fm_model
        self.config = config

    def recommend(self, student: dict, top_k: int = 10) -> list:
        """Run the 3-stage cascade for one student.

        Returns list of dicts:
            {item_id, stage1_eligibility, stage2_cf_score, stage3_fm_score}
        """
        raise NotImplementedError("Phase 4")
