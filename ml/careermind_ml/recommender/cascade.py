"""Cascade orchestrator (paper Sec. V-B; Burke's [3] cascade hybrid pattern).

Stage 1: knowledge-graph candidate generation (>= 60% prerequisites)
Stage 2: FES-weighted item-to-item CF re-ranking
Stage 3: FES-augmented FM final scoring

Returns ranked recommendations WITH per-stage provenance so the LLM
explanation layer (NFR07) can cite why each item ranked.

Cold start (FR11): a student with no skill assessments is evaluated against
the POPULATION-AVERAGE skill profile; recommendations personalise as the
student's own assessments arrive.
"""
import numpy as np
import torch

from .cf import cf_rerank, item_cooccurrence, student_history_items
from .features import vectorize
from .fm import load_artifact
from .knowledge_graph import generate_candidates, load_knowledge_graph


class CascadeRecommender:
    def __init__(self, graph, cooc: dict, fm_model, fm_spec, population_skills: dict, config: dict | None = None):
        self.graph = graph
        self.cooc = cooc
        self.fm_model = fm_model
        self.fm_spec = fm_spec
        self.population_skills = population_skills
        self.config = config or {}

    # ------------------------------------------------------------- factories

    @classmethod
    def from_data(cls, data: dict, config: dict | None = None) -> "CascadeRecommender":
        """Build from the load_fm_training_data dict + the trained FM artifact."""
        import torch

        fes_by_session = data.get("fes_by_session") or {}

        cooc = item_cooccurrence(data["interactions"], fes_by_session)
        fm_model, fm_spec = load_artifact()

        population_skills = {}
        skill_counts: dict[str, list[int]] = {}
        for skills in data.get("skills_by_student", {}).values():
            for skill, level in skills.items():
                skill_counts.setdefault(skill, []).append(level)
        if skill_counts:
            population_skills = {s: float(np.mean(v)) for s, v in skill_counts.items()}

        graph = load_knowledge_graph()
        return cls(graph, cooc, fm_model, fm_spec, population_skills, config)

    @classmethod
    def from_mongo(cls, uri: str = "mongodb://localhost:27017", db_name: str = "careermind", config: dict | None = None) -> "CascadeRecommender":
        from .features import load_fm_training_data

        data = load_fm_training_data(uri, db_name)
        from pymongo import MongoClient

        client = MongoClient(uri)
        fes_by_session = {
            row["session"]: row["fes"] for row in client[db_name].fes_history.find({}, {"session": 1, "fes": 1})
        }
        data["fes_by_session"] = fes_by_session
        return cls.from_data(data, config)

    # ------------------------------------------------------------ inference

    def recommend(self, student_agg: dict, student_skills: dict | None, student_items: list[str] | None, top_k: int = 10) -> dict:
        """Run the 3-stage cascade for one student.

        Args:
            student_agg: features.py-style aggregate (grades, fes_current,
                fes_trend, preferences, year_of_study).
            student_skills: {skill_id: level 1-5}; None/empty -> population profile.
            student_items: engaged item ids (CF history); may be empty.
        Returns:
            {"results": [...top_k...], "cold_start": bool}
        """
        student_items = student_items or []
        cold_start = not student_skills
        skills = student_skills or self.population_skills
        if not skills:
            # degenerate: no population either (e.g. empty DB) -> all careers pass
            skills = {}

        # Stage 1: knowledge-graph eligibility (>= 60% prerequisites)
        candidates = generate_candidates(skills, self.graph, threshold=self.config.get("stage1_eligibility_threshold", 0.60))
        if not candidates:
            return {"results": [], "cold_start": cold_start}

        # Stage 2: FES-weighted CF re-ranking
        re_ranked = cf_rerank(candidates, self.cooc, student_items)

        # Stage 3: FES-augmented FM scoring
        results = []
        for candidate in re_ranked:
            x = vectorize(student_agg, candidate["id"], self.fm_spec)
            with torch.no_grad():
                score = float(self.fm_model(torch.as_tensor(x).unsqueeze(0)).item())
            results.append(
                {
                    "id": candidate["id"],
                    "name": candidate["name"],
                    "category": candidate["category"],
                    "stage1_eligibility": candidate["eligibility"],
                    "prerequisites_met": candidate["prerequisites_met"],
                    "stage2_cf_score": round(candidate["stage2_cf_score"], 4),
                    "stage3_fm_score": round(score, 4),
                    "contributing_features": {
                        "fes_current": student_agg.get("fes_current"),
                        "fes_trend": student_agg.get("fes_trend"),
                        "top_preference": max((student_agg.get("preferences") or {"—": 0}).items(), key=lambda kv: kv[1])[0],
                        "prerequisites_met": candidate["prerequisites_met"],
                    },
                }
            )
        results.sort(key=lambda r: (-r["stage3_fm_score"], -r["stage2_cf_score"], r["id"]))
        return {"results": results[:top_k], "cold_start": cold_start}
