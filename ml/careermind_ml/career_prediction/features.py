"""Training/inference features for the career path predictor (paper Sec. V-D).

Feature groups:
  * cumulative academic performance
  * skill-domain strength       — per-category assessment counts and levels
                                  relative to the student's own mean
                                  (skill -> category via KG prerequisites)
  * experiential-learning participation — sessions, interactions, distinct
                                  items, mean session duration
  * FES trajectory (current + 14-day trend)
  * stated career preferences  — normalised category weights (uniform 1/6
                                  where unstated)

NOTE on the preference group: the simulator derives seeded career_preferences
from the same latent vector that determines the career_outcome label, so
preferences almost encode the answer. `include_preferences` therefore defaults
to True for the paper-exact model but training ALWAYS prints a no-preference
ablation so the pilot study can report honest numbers (Phase 5 decision).

Missing values fall back to training-population column means (same convention
as the FM feature builder), so brand-new users always get a valid row.
"""
import pathlib

import numpy as np
import pandas as pd

from careermind_ml.fes.trend import compute_fes_trend
from careermind_ml.recommender.features import (
    CAREER_CATEGORIES,
    DEFAULT_YEAR_OF_STUDY,
    GRADE_SUBJECTS,
)

SEED_PATH = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_graph" / "careers_seed.json"

GRADE_COLUMNS = tuple(f"grade_{s}" for s in GRADE_SUBJECTS)
SKILL_COUNT_COLUMNS = tuple(f"skill_count_{c}" for c in CAREER_CATEGORIES)
SKILL_LEVEL_COLUMNS = tuple(f"skill_level_{c}" for c in CAREER_CATEGORIES)
SKILL_COLUMNS = SKILL_COUNT_COLUMNS + SKILL_LEVEL_COLUMNS
EXPERIENTIAL_COLUMNS = ("exp_sessions", "exp_interactions", "exp_distinct_items", "exp_mean_duration")
FES_COLUMNS = ("fes_current", "fes_trend")
CONTEXT_COLUMNS = ("year",)
PREFERENCE_COLUMNS = tuple(f"pref_{c}" for c in CAREER_CATEGORIES)
BASE_COLUMNS = GRADE_COLUMNS + SKILL_COLUMNS + EXPERIENTIAL_COLUMNS + FES_COLUMNS + CONTEXT_COLUMNS
ALL_COLUMNS = BASE_COLUMNS + PREFERENCE_COLUMNS

# clip-scaled so typical values land in ~[0, 1] (simulator: 12 sessions,
# ~22 interactions, ~11 distinct items, ~45-minute sessions)
_EXPERIENTIAL_SCALES = {"exp_sessions": 24.0, "exp_interactions": 60.0, "exp_distinct_items": 12.0, "exp_mean_duration": 60.0}


def load_skill_categories(seed_path: str | pathlib.Path = SEED_PATH) -> dict[str, set[str]]:
    """skill -> career categories whose pathways list it as a prerequisite."""
    import json

    with open(seed_path) as fh:
        seed = json.load(fh)
    mapping: dict[str, set[str]] = {}
    for career in seed.get("careers", []):
        for prereq in career.get("prerequisites", []):
            mapping.setdefault(prereq["skill"], set()).add(career["category"])
    return mapping


def feature_row(
    student: dict,
    skill_categories: dict[str, set[str]],
    include_preferences: bool = True,
    population_defaults: dict[str, float] | None = None,
) -> dict:
    """One student -> one feature row (dict of column -> value).

    `student` agg: {grades, skills, participation, fes_current, fes_trend,
    preferences, year_of_study}. Population-default fills mirror the FM
    feature builder (grades in raw 0-100 here, scaled at frame level).
    """
    defaults = population_defaults or {}
    row: dict[str, float] = {}

    grades = student.get("grades") or {}
    for subject, column in zip(GRADE_SUBJECTS, GRADE_COLUMNS):
        value = grades.get(subject)
        if value is None:
            row[column] = defaults.get(column, 0.7)  # already scaled
        else:
            row[column] = float(value) / 100.0

    # skill-domain strength: WHICH domains were assessed (count, the strong
    # signal — simulator samples assessments ~ affinity) plus the level
    # RELATIVE to the student's own mean (absolute levels are dominated by
    # ability; centering removes that offset)
    skills = student.get("skills") or {}
    overall_level = float(np.mean(list(skills.values()))) if skills else 0.0
    for category in CAREER_CATEGORIES:
        in_category = [level for skill, level in skills.items() if category in skill_categories.get(skill, set())]
        count_col = f"skill_count_{category}"
        level_col = f"skill_level_{category}"
        if not skills:
            # no assessments at all: population-average profile (cold start)
            row[count_col] = defaults.get(count_col, 0.25)
            row[level_col] = defaults.get(level_col, 0.0)
        else:
            row[count_col] = float(np.clip(len(in_category) / 6.0, 0.0, 1.0))
            if in_category:
                row[level_col] = float(np.clip((float(np.mean(in_category)) - overall_level) / 2.0, -1.0, 1.0))
            else:
                row[level_col] = 0.0

    participation = student.get("participation") or {}
    for column in EXPERIENTIAL_COLUMNS:
        value = participation.get(column)
        if value is None:
            row[column] = defaults.get(column, 0.0)
        else:
            row[column] = float(np.clip(value / _EXPERIENTIAL_SCALES[column], 0.0, 1.0))

    fes = student.get("fes_current")
    row["fes_current"] = float(fes) if fes is not None else defaults.get("fes_current", 0.5)
    trend = student.get("fes_trend")
    row["fes_trend"] = float(trend) if trend is not None else defaults.get("fes_trend", 0.5)

    year = student.get("year_of_study") or DEFAULT_YEAR_OF_STUDY
    row["year"] = float(year) / 6.0

    if include_preferences:
        prefs = student.get("preferences") or {}
        total = sum(prefs.values()) if prefs else 0.0
        for category, column in zip(CAREER_CATEGORIES, PREFERENCE_COLUMNS):
            if prefs and total > 0:
                row[column] = float(prefs.get(category, 0.0)) / total
            else:
                row[column] = 1.0 / len(CAREER_CATEGORIES)

    return row


def build_feature_frame(
    students: list[dict],
    include_preferences: bool = True,
    population_defaults: dict[str, float] | None = None,
    skill_categories: dict[str, set[str]] | None = None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Assemble the (X, defaults) pair; labels are NOT part of the frame.

    Population defaults are the column means of this population (training)
    or taken from the artifact (serving) so cold users are filled the same
    way the model was trained.
    """
    skill_categories = skill_categories or load_skill_categories()

    # pass 1 (training only): compute population column means
    if population_defaults is None:
        rows = [feature_row(s, skill_categories, include_preferences) for s in students]
        frame = pd.DataFrame(rows, columns=list(BASE_COLUMNS) + (list(PREFERENCE_COLUMNS) if include_preferences else []))
        # recompute with defaults (fill each column's NaN with its own mean)
        population_defaults = {c: float(frame[c].mean()) for c in frame.columns}

    rows = [
        feature_row(s, skill_categories, include_preferences, population_defaults)
        for s in students
    ]
    columns = ALL_COLUMNS if include_preferences else BASE_COLUMNS
    frame = pd.DataFrame(rows, columns=list(columns))
    return frame, population_defaults


# ------------------------------------------------------------- Mongo loader

def load_ensemble_training_data(uri: str = "mongodb://localhost:27017", db_name: str = "careermind") -> dict:
    """Everything train_ensemble needs from MongoDB (pymongo, lazy import).

    Only profiles carrying a career_outcome label are returned (the
    simulator population; OULAD profiles have no career labels).
    """
    import os

    from pymongo import MongoClient

    client = MongoClient(os.getenv("MONGO_URI", uri))
    db = client[os.getenv("MONGO_DB_NAME", db_name)]

    fes_by_student: dict[str, list[tuple]] = {}
    for row in db.fes_history.find({}, {"student": 1, "fes": 1, "computed_at": 1}).sort("computed_at", 1):
        fes_by_student.setdefault(row["student"], []).append((row["computed_at"], row["fes"]))

    participation: dict[str, dict] = {}
    for row in db.sessions.aggregate(
        [
            {"$group": {"_id": "$student", "sessions": {"$sum": 1}, "mean_duration": {"$avg": "$duration_minutes"}}},
        ]
    ):
        if row["_id"] is None:
            continue
        participation[str(row["_id"])] = {
            "exp_sessions": row["sessions"],
            "exp_interactions": 0,
            "exp_distinct_items": 0,
            "exp_mean_duration": row["mean_duration"],
        }
    for row in db.interactions.aggregate(
        [
            {"$group": {"_id": "$student", "interactions": {"$sum": 1}, "items": {"$addToSet": "$item_id"}}},
        ]
    ):
        if row["_id"] is None:
            continue
        part = participation.setdefault(
            str(row["_id"]), {"exp_sessions": 0, "exp_interactions": 0, "exp_distinct_items": 0, "exp_mean_duration": None}
        )
        part["exp_interactions"] = row["interactions"]
        part["exp_distinct_items"] = len(row["items"])

    students = []
    for profile in db.profiles.find({"career_outcome": {"$exists": True}}, {"_id": 0}):
        student = profile.get("external_id") or profile.get("email")
        series = fes_by_student.get(student, [])
        fes_current = series[-1][1] if series else None
        fes_trend = compute_fes_trend(series)
        students.append(
            {
                "student": student,
                "grades": {r.get("subject"): r.get("grade") for r in profile.get("academic_records") or []},
                "skills": {
                    s["skill"]: max(1, min(5, int(s["score"] // 20) + 1))
                    for s in profile.get("skill_assessments") or []
                },
                "participation": participation.get(student, {}),
                "fes_current": fes_current,
                "fes_trend": fes_trend,
                "preferences": {p.get("category"): p.get("weight") for p in profile.get("career_preferences") or []},
                "year_of_study": profile.get("year_of_study", DEFAULT_YEAR_OF_STUDY),
                "label": profile.get("career_outcome", {}).get("category"),
                "pathway_id": profile.get("career_outcome", {}).get("pathway_id"),
            }
        )
    return {"students": students}
