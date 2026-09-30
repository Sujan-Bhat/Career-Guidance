"""Feature construction for the FES-augmented FM (paper Sec. V-B, Stage 3).

Student feature vector (concatenated with a one-hot item vector):
  * academic      — 5 key subject grades (population mean where missing)
  * behavioural   — current FES + normalised 14-day FES trend
  * preference    — 6 career-category affinities (uniform where missing)
  * contextual    — year of study / 6
  * item          — one-hot over the item vocabulary (pathways + courses)

Missing values fall back to population defaults so brand-new users get
valid vectors (consistent with the FR11 cold-start decision).
"""
from dataclasses import dataclass, field

import numpy as np

from ..fes.trend import compute_fes_trend

GRADE_SUBJECTS = ("CS201", "CS230", "CS320", "ST210", "CS350")
CAREER_CATEGORIES = ("software", "data", "infrastructure", "security", "hardware", "management")
DEFAULT_YEAR_OF_STUDY = 3

STUDENT_DIM = len(GRADE_SUBJECTS) + 2 + len(CAREER_CATEGORIES) + 1  # 14


@dataclass
class FeatureSpec:
    item_vocab: list[str]
    population_grades: dict = field(default_factory=dict)
    population_fes: float = 0.5
    population_trend: float = 0.5

    @property
    def dim(self) -> int:
        return STUDENT_DIM + len(self.item_vocab)


def build_spec(
    students_agg: list[dict],
    item_vocab: list[str],
) -> FeatureSpec:
    """Derive population defaults (means) from the training population."""
    grades: dict[str, list[float]] = {s: [] for s in GRADE_SUBJECTS}
    fes_values, trends = [], []
    for agg in students_agg:
        for subject in GRADE_SUBJECTS:
            value = (agg.get("grades") or {}).get(subject)
            if value is not None:
                grades[subject].append(float(value))
        if agg.get("fes_current") is not None:
            fes_values.append(float(agg["fes_current"]))
        if agg.get("fes_trend") is not None:
            trends.append(float(agg["fes_trend"]))
    return FeatureSpec(
        item_vocab=item_vocab,
        population_grades={s: float(np.mean(v)) if v else 70.0 for s, v in grades.items()},
        population_fes=float(np.mean(fes_values)) if fes_values else 0.5,
        population_trend=float(np.mean(trends)) if trends else 0.5,
    )


def vectorize(agg: dict, item_id: str, spec: FeatureSpec) -> np.ndarray:
    """One (student, item) feature vector, values in ~[0, 1]."""
    parts = []

    for subject in GRADE_SUBJECTS:
        value = (agg.get("grades") or {}).get(subject)
        parts.append(float(value) / 100.0 if value is not None else spec.population_grades[subject] / 100.0)

    fes = agg.get("fes_current")
    parts.append(float(fes) if fes is not None else spec.population_fes)
    trend = agg.get("fes_trend")
    parts.append(float(trend) if trend is not None else spec.population_trend)

    prefs = agg.get("preferences") or {}
    total_pref = sum(prefs.values()) if prefs else 0.0
    for category in CAREER_CATEGORIES:
        if prefs and total_pref > 0:
            parts.append(float(prefs.get(category, 0.0)) / total_pref)
        else:
            parts.append(1.0 / len(CAREER_CATEGORIES))

    year = agg.get("year_of_study") or DEFAULT_YEAR_OF_STUDY
    parts.append(float(year) / 6.0)

    one_hot = np.zeros(len(spec.item_vocab))
    if item_id in spec.item_vocab:
        one_hot[spec.item_vocab.index(item_id)] = 1.0
    parts.append(one_hot)

    return np.concatenate([np.asarray(parts[:STUDENT_DIM], dtype=np.float32), one_hot.astype(np.float32)])


def make_dataset(
    interactions: list[dict],
    students_agg: list[dict],
    spec: FeatureSpec,
    negatives_per_positive: float = 2.0,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Binary implicit-feedback dataset: engaged items = 1, uniformly sampled
    non-engaged items per student = 0 (ratio per config)."""
    rng = rng or np.random.default_rng(0)
    by_student: dict[str, dict] = {agg["student"]: agg for agg in students_agg}
    engaged: dict[str, set[str]] = {}
    for interaction in interactions:
        engaged.setdefault(interaction["student"], set()).add(interaction["item_id"])

    features, labels = [], []
    for interaction in interactions:
        agg = by_student.get(interaction["student"])
        if agg is None:
            continue
        features.append(vectorize(agg, interaction["item_id"], spec))
        labels.append(1.0)
        n_negatives = int(negatives_per_positive)
        if negatives_per_positive > int(negatives_per_positive) and rng.random() < negatives_per_positive - n_negatives:
            n_negatives += 1
        for _ in range(n_negatives):
            candidate = None
            for _attempt in range(64):  # bounded: a student engaged in every item has no negatives
                trial = spec.item_vocab[int(rng.integers(0, len(spec.item_vocab)))]
                if trial not in engaged.get(interaction["student"], set()):
                    candidate = trial
                    break
            if candidate is None:
                continue
            features.append(vectorize(agg, candidate, spec))
            labels.append(0.0)

    return np.vstack(features), np.asarray(labels, dtype=np.float32)


# ------------------------------------------------------------- Mongo loaders

def load_fm_training_data(uri: str = "mongodb://localhost:27017", db_name: str = "careermind") -> dict:
    """Assemble everything train_fm needs from MongoDB (pymongo, lazy import)."""
    import os

    from pymongo import MongoClient

    client = MongoClient(uri or os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client[db_name or os.getenv("MONGO_DB_NAME", "careermind")]

    interactions = list(db.interactions.find({}, {"_id": 0}))
    profiles = list(db.profiles.find({}, {"_id": 0}))

    # latest FES + 14-day trend per student from fes_history
    fes_by_student: dict[str, list[tuple]] = {}
    for row in db.fes_history.find({}, {"student": 1, "fes": 1, "computed_at": 1}).sort("computed_at", 1):
        fes_by_student.setdefault(row["student"], []).append((row["computed_at"], row["fes"]))

    students_agg = []
    skills_by_student = {}
    for profile in profiles:
        student = profile.get("external_id") or str(profile.get("_id", ""))
        grades = {
            r.get("subject"): r.get("grade")
            for r in profile.get("academic_records") or []
        }
        series = fes_by_student.get(student, [])
        fes_current = series[-1][1] if series else None
        fes_trend = compute_fes_trend(series)
        preferences = profile.get("latents", {}).get("domain_affinity") or {
            p.get("category"): p.get("weight") for p in profile.get("career_preferences") or []
        }
        students_agg.append(
            {
                "student": student,
                "grades": grades,
                "fes_current": fes_current,
                "fes_trend": fes_trend,
                "preferences": preferences,
                "year_of_study": profile.get("year_of_study", DEFAULT_YEAR_OF_STUDY),
            }
        )
        skills = {
            s["skill"]: max(1, min(5, int(s["score"] // 20) + 1))
            for s in profile.get("skill_assessments") or []
        }
        if skills:
            skills_by_student[student] = skills

    item_vocab = sorted({i["item_id"] for i in interactions})
    return {
        "interactions": interactions,
        "students_agg": students_agg,
        "skills_by_student": skills_by_student,
        "item_vocab": item_vocab,
    }
