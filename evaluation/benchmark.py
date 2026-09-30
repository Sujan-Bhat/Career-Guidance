"""Leave-one-out recommender benchmark (paper Sec. VIII #2).

Holdout protocol: per student, the LAST interacted item (by date) is held
out as the single relevant item; every technique ranks ALL career pathways
using only the remaining (train) history. Reported: P@10, R@10, nDCG@10,
Hit@10 averaged over students with >= 2 interactions.

Shared context (build_context) loads Mongo once and hands the same inputs
to the cascade and to each single-technique baseline.
"""
import os
from collections import defaultdict

from pymongo import MongoClient

from baselines import SingleTechniqueBaseline
from careermind_ml.recommender.cf import item_cooccurrence
from careermind_ml.recommender.cascade import CascadeRecommender
from careermind_ml.recommender.knowledge_graph import get_careers, load_knowledge_graph

TECHNIQUES = ("cascade", "kg_only", "cf_only", "fm_only", "popularity")


def _student_agg(profile: dict, fes_series: list) -> dict:
    grades = {r.get("subject"): r.get("grade") for r in profile.get("academic_records") or []}
    from careermind_ml.fes.trend import compute_fes_trend

    return {
        "student": profile.get("external_id") or str(profile.get("_id", "")),
        "grades": grades,
        "fes_current": fes_series[-1][1] if fes_series else None,
        "fes_trend": compute_fes_trend(fes_series),
        "preferences": profile.get("latents", {}).get("domain_affinity")
        or {p.get("category"): p.get("weight") for p in profile.get("career_preferences") or []},
        "year_of_study": profile.get("year_of_study") or 3,
    }


def build_context(uri: str | None = None, db_name: str | None = None) -> dict:
    """Load Mongo once: train/holdout split, per-student inputs, cascade,
    and the four baselines — all trained/built on the TRAIN split only
    (the stage-3 FM is retrained here; the shared fm.pt artifact saw the
    holdouts during its own training and would leak them into scoring)."""
    uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = db_name or os.getenv("MONGO_DB_NAME", "careermind")
    db = MongoClient(uri)[db_name]

    interactions = list(db.interactions.find({}, {"_id": 0}))
    fes_by_session = {
        row["session"]: row["fes"] for row in db.fes_history.find({}, {"session": 1, "fes": 1})
    }
    profiles = list(db.profiles.find({}, {"_id": 1, "external_id": 1, "academic_records": 1,
                                          "skill_assessments": 1, "career_preferences": 1,
                                          "latents": 1, "year_of_study": 1}))

    # --- split: hold out each student's last interacted item -------------
    by_student: dict[str, list[dict]] = defaultdict(list)
    for ix in interactions:
        by_student[ix["student"]].append(ix)
    holdouts: dict[str, str] = {}
    train_interactions = []
    for student, rows in by_student.items():
        rows.sort(key=lambda r: (r.get("date") or "", r.get("item_id") or ""))
        if len(rows) >= 2:
            holdouts[student] = rows[-1]["item_id"]
            train_interactions.extend(rows[:-1])
        else:
            train_interactions.extend(rows)

    # --- per-student inputs ---------------------------------------------
    fes_by_student: dict[str, list[tuple]] = defaultdict(list)
    for row in db.fes_history.find({}, {"student": 1, "fes": 1, "computed_at": 1}).sort("computed_at", 1):
        fes_by_student[row["student"]].append((row["computed_at"], row["fes"]))

    skills_by_student: dict[str, dict] = {}
    all_aggs: list[dict] = []
    students = []
    for profile in profiles:
        student = profile.get("external_id") or str(profile.get("_id", ""))
        agg = _student_agg(profile, fes_by_student.get(student, []))
        all_aggs.append(agg)
        skills = {
            s["skill"]: max(1, min(5, int(s["score"] // 20) + 1))
            for s in profile.get("skill_assessments") or []
        }
        if skills:
            skills_by_student[student] = skills
        if student in holdouts:
            history = [r["item_id"] for r in by_student[student][:-1]]
            students.append(
                {
                    "student": student,
                    "agg": agg,
                    "skills": skills,
                    "history": list(dict.fromkeys(history)),
                    "relevant": holdouts[student],
                }
            )

    # --- cascade + baselines on the TRAIN split -------------------------
    data = {
        "interactions": train_interactions,
        "fes_by_session": fes_by_session,
        "skills_by_student": skills_by_student,
    }
    cascade = CascadeRecommender.from_data(data)

    # Leakage fix: from_data loads the pre-trained fm.pt artifact, which was
    # trained on ALL interactions — including the holdouts this benchmark
    # scores. Retrain the FM on the train split only (defaults mirror
    # ml/configs/fm.yaml) and swap it into the cascade and the fm_only
    # baseline so every technique is graded on unseen items.
    from careermind_ml.recommender.features import build_spec
    from careermind_ml.recommender.fm import fit_fm

    fm_item_vocab = sorted({ix["item_id"] for ix in train_interactions})
    fm_spec = build_spec(all_aggs, fm_item_vocab)
    fm_model, _fit = fit_fm(train_interactions, all_aggs, fm_spec)
    cascade.fm_model = fm_model
    cascade.fm_spec = fm_spec

    graph = cascade.graph
    candidates = sorted(c["id"] for c in get_careers(graph))

    baselines = {
        "kg_only": SingleTechniqueBaseline("kg_only", graph=graph),
        "cf_only": SingleTechniqueBaseline("cf_only", cooc=cascade.cooc),
        "fm_only": SingleTechniqueBaseline("fm_only", fm_model=fm_model, fm_spec=fm_spec),
        "popularity": SingleTechniqueBaseline(
            "popularity",
            interactions=train_interactions,
            fes_by_session=fes_by_session,
        ),
    }
    return {
        "cascade": cascade,
        "baselines": baselines,
        "students": students,
        "candidates": candidates,
        "n_train_interactions": len(train_interactions),
        "n_holdouts": len(holdouts),
    }


def _populate_skills(skills: dict | None, cascade: CascadeRecommender) -> dict:
    """Same cold-start rule as serving: own skills or population profile."""
    return skills or cascade.population_skills or {}


def run_benchmark(context: dict, top_k: int = 10, threshold: float | None = None) -> dict:
    """Rank with every technique and average the metrics (paper Sec. VIII #2).

    `threshold` overrides the cascade's Stage-1 eligibility gate (used by the
    sensitivity sweep); baselines are unaffected by it."""
    from metrics import precision_at_k, recall_at_k, ndcg_at_k
    from careermind_ml.recommender.knowledge_graph import generate_candidates

    cascade = context["cascade"]
    if threshold is not None:
        cascade.config["stage1_eligibility_threshold"] = threshold
    gate = threshold if threshold is not None else cascade.config.get("stage1_eligibility_threshold", 0.60)

    scores = {
        name: {"precision@k": [], "recall@k": [], "ndcg@k": [], "hit@k": []}
        for name in TECHNIQUES
    }
    gated_counts = []
    for student in context["students"]:
        relevant = {student["relevant"]}
        skills = _populate_skills(student["skills"], cascade)
        gated_counts.append(len(generate_candidates(skills, cascade.graph, threshold=gate)))

        rankings = {}
        result = cascade.recommend(student["agg"], skills, student["history"], top_k=top_k)
        rankings["cascade"] = [r["id"] for r in result["results"]]
        for name, baseline in context["baselines"].items():
            rankings[name] = baseline.rank(
                {"skills": skills, "agg": student["agg"], "history": student["history"]},
                context["candidates"],
            )[:top_k]

        for name, ranked in rankings.items():
            scores[name]["precision@k"].append(precision_at_k(ranked, relevant, top_k))
            scores[name]["recall@k"].append(recall_at_k(ranked, relevant, top_k))
            scores[name]["ndcg@k"].append(ndcg_at_k(ranked, relevant, top_k))
            scores[name]["hit@k"].append(1.0 if relevant & set(ranked[:top_k]) else 0.0)

    metrics = {
        name: {metric: (sum(values) / len(values) if values else 0.0) for metric, values in per.items()}
        for name, per in scores.items()
    }
    if threshold is not None:
        cascade.config["stage1_eligibility_threshold"] = 0.60  # restore default
    return {
        "n_students": len(context["students"]),
        "top_k": top_k,
        "threshold": threshold,
        "mean_candidates": (sum(gated_counts) / len(gated_counts) if gated_counts else 0.0),
        "metrics": metrics,
    }
