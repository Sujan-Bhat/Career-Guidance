"""Batch FES pipeline over MongoDB (Phase 2).

Implements the paper's session-end FES computation in batch form:

  1. Load behavioural sessions per student (sorted by date).
  2. Compute the five sub-metrics per session (SCI uses the trailing
     14-day window of that student's sessions).
  3. Calibrate the population-level weight vector (Eq. 2, pooled pairs),
     then per-student vectors (gated: >= 8 sessions, >= 2 outcomes, every
     sub-metric >= 3 non-missing observations; else population fallback).
  4. Compute FES per session (Eq. 1, renormalised over present sub-metrics).
  5. Persist `fes_history` (FESScore rows) and `fes_weights`
     (per-student rows + one population row with student=None).

This pipeline OWNS those two collections during Phase 2 (rewrite in full on
each run). Phase 3 adds the Celery session-end hook alongside it; the nightly
Celery beat job uses `recalibrate_weights`, which upserts weights and refreshes
existing rows in place instead of deleting them.

Usage:
    PYTHONPATH=ml python -m careermind_ml.fes.pipeline \
        [--uri mongodb://localhost:27017] [--db careermind] [--config ml/configs/fes.yaml]
"""
import argparse
import os
import pathlib
import sys
from datetime import datetime, timedelta

import yaml

from .submetrics import (
    DEFAULT_LRDS_THRESHOLDS,
    distraction_free_engagement_time,
    learning_resource_depth_score,
    quiz_attempt_persistence,
    session_consistency_index,
    task_completion_rate,
)
from .weights import (
    SESSION_LOCAL_SUBMETRICS,
    SUBMETRICS,
    calibrate_population_weights,
    calibrate_student_weights,
    compute_fes,
)

DEFAULT_CONFIG_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "configs" / "fes.yaml"


def load_config(path: str | pathlib.Path | None) -> dict:
    config = {}
    if path and pathlib.Path(path).exists():
        with open(path) as fh:
            config = yaml.safe_load(fh) or {}
    weight_cfg = dict(config.get("weight_calibration", {}))
    weight_cfg = {
        "min_sessions": weight_cfg.get("min_sessions", 8),
        "min_graded_outcomes": weight_cfg.get("min_graded_outcomes", 2),
        "min_nonmissing_per_submetric": weight_cfg.get("min_nonmissing_per_submetric", 3),
    }
    return {
        "sci_window_days": config.get("sci_window_days", 14),
        "lrds_thresholds": {
            **DEFAULT_LRDS_THRESHOLDS,
            **{
                k: v
                for k, v in (config.get("lrds_dwell_thresholds_seconds") or {}).items()
            },
        },
        "weight_calibration": weight_cfg,
    }


def compute_session_metrics(session: dict, window: list[dict], config: dict) -> dict:
    """Five sub-metrics for one session. `window` is the student's sessions
    in the trailing 14-day window (inclusive of the current session)."""
    metrics = {
        "tcr": task_completion_rate(session.get("tasks_started"), session.get("tasks_completed")),
        "dfet": distraction_free_engagement_time(
            session.get("resource_visits") or [], session.get("duration_minutes")
        ),
        "qap": quiz_attempt_persistence(
            session.get("quiz_items"), session.get("quiz_items_correct"), session.get("quiz_reattempts")
        ),
        "lrds": learning_resource_depth_score(
            session.get("resource_visits") or [], config["lrds_thresholds"]
        ),
    }
    if window:
        metrics["sci"] = session_consistency_index(
            [
                w.get("login_minute_of_day")
                for w in window
                if w.get("login_minute_of_day") is not None and w.get("duration_minutes")
            ],
            [w.get("duration_minutes") for w in window if w.get("login_minute_of_day") is not None and w.get("duration_minutes")],
        )
    else:
        metrics["sci"] = None
    return metrics


def _session_datetime(session: dict) -> datetime:
    base = datetime.fromisoformat(session["date"])
    minute = session.get("login_minute_of_day", 0)
    return base + timedelta(minutes=int(minute))


def session_key(session: dict) -> str:
    """Canonical FES session key shared with the Celery session-end task.

    Simulator sessions use `{student}:{session_index}`; collector sessions
    have no session_index, so they key on the Mongo `_id` (matching
    apps.fes.tasks). Previously live rows collapsed onto `student:None`.
    """
    index = session.get("session_index")
    if index is not None:
        return f"{session['student']}:{index}"
    return f"{session['student']}:{session.get('_id')}"


def _load_session_groups(db) -> dict[str, list[dict]]:
    """Completed simulator/collector sessions grouped by student, each sorted."""
    sessions = list(
        db.sessions.find(
            {
                "source": {"$in": ["simulator", "collector"]},
                # only completed sessions carry the aggregates the FES engine
                # reads; "active" sessions lack `date` and would KeyError below
                "status": "completed",
                "date": {"$exists": True, "$ne": None},
            }
        )
    )
    by_student: dict[str, list[dict]] = {}
    for session in sessions:
        by_student.setdefault(session["student"], []).append(session)
    for sess in by_student.values():
        sess.sort(key=lambda s: (s["date"], s.get("session_index", 0)))
    return by_student


def _pass_submetrics(by_student: dict, config: dict) -> tuple[dict, list[dict]]:
    """Per-session sub-metrics (+ trailing SCI window) and outcome pairs."""
    student_metrics: dict[str, list[tuple[dict, dict]]] = {}
    all_pairs: list[dict] = []
    for student, sess in by_student.items():
        computed = []
        for i, session in enumerate(sess):
            session_date = datetime.fromisoformat(session["date"]).date()
            window = [
                w
                for w in sess[: i + 1]
                if (session_date - datetime.fromisoformat(w["date"]).date()).days
                <= config["sci_window_days"]
            ]
            # SCI window inputs: None login times / durations would crash the
            # circular-std math (math.sin(None)); skip them like tasks.py does
            metrics = compute_session_metrics(session, window, config)
            computed.append((session, metrics))
            all_pairs.append({**metrics, "outcome": session.get("assessment_score")})
        student_metrics[student] = computed
    return student_metrics, all_pairs


def _pass_weights(student_metrics: dict, all_pairs: list[dict], config: dict) -> tuple[list[dict], dict, int]:
    """Population vector first, then gated per-student vectors (Eq. 2).

    Returns (weight rows, population weights, students on population fallback).
    """
    population_weights = calibrate_population_weights(all_pairs, config["weight_calibration"])

    rows = [
        {
            "student": None,  # population-level cold-start vector
            "weights": population_weights,
            "n_sessions": len(all_pairs),
            "n_graded_outcomes": sum(1 for p in all_pairs if p.get("outcome") is not None),
            "computed_at": datetime.utcnow(),
        }
    ]
    students_on_population = 0
    for student, computed in student_metrics.items():
        pairs = [
            {**metrics, "outcome": session.get("assessment_score")} for session, metrics in computed
        ]
        weights = calibrate_student_weights(pairs, config["weight_calibration"])
        if weights is None:
            weights = population_weights
            students_on_population += 1
        rows.append(
            {
                "student": student,
                "weights": weights,
                "n_sessions": len(pairs),
                "n_graded_outcomes": sum(1 for p in pairs if p.get("outcome") is not None),
                "computed_at": datetime.utcnow(),
            }
        )
    return rows, population_weights, students_on_population


def run_pipeline(
    uri: str | None = None,
    db_name: str | None = None,
    config_path: str | pathlib.Path | None = None,
) -> dict:
    """Execute the full FES batch pipeline; returns a summary dict.

    DESTRUCTIVE: owns `fes_history` and `fes_weights` and rewrites both from
    scratch. Use `recalibrate_weights` for the nightly beat job, which must
    not wipe rows written by the live session-end task.
    """
    try:
        from pymongo import MongoClient
    except ImportError:
        print("pymongo is required: pip install pymongo")
        sys.exit(1)

    config = load_config(config_path)
    client = MongoClient(uri or os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client[db_name or os.getenv("MONGO_DB_NAME", "careermind")]

    by_student = _load_session_groups(db)
    student_metrics, all_pairs = _pass_submetrics(by_student, config)
    fes_weight_rows, population_weights, students_on_population = _pass_weights(
        student_metrics, all_pairs, config
    )

    fes_rows = []
    for student, computed in student_metrics.items():
        weights = next(
            row["weights"] for row in fes_weight_rows if row["student"] == student
        )
        for session, metrics in computed:
            if all(metrics.get(m) is None for m in SESSION_LOCAL_SUBMETRICS):
                # signal-less session: no session-local sub-metric at all, so
                # Eq. 1 would collapse onto SCI (mirrors the live-task guard
                # in apps.fes.tasks.compute_session_fes) — skip the row
                continue
            fes = compute_fes(metrics, weights)
            if fes is None:
                continue
            fes_rows.append(
                {
                    "session": session_key(session),
                    "student": student,
                    **{m: metrics.get(m) for m in SUBMETRICS},
                    "fes": fes,
                    "weights": weights,
                    "computed_at": _session_datetime(session),
                }
            )

    # ---- pass 3: persist (pipeline owns these collections in Phase 2) ----
    db.fes_history.delete_many({})
    db.fes_weights.delete_many({})
    if fes_rows:
        db.fes_history.insert_many(fes_rows)
    if fes_weight_rows:
        db.fes_weights.insert_many(fes_weight_rows)

    summary = {
        "students": len(by_student),
        "sessions": sum(len(v) for v in by_student.values()),
        "fes_rows": len(fes_rows),
        "students_on_population": students_on_population,
        "population_weights": {k: round(v, 4) for k, v in population_weights.items()},
    }
    print(
        f"FES pipeline: {summary['students']} students, {summary['sessions']} sessions -> "
        f"{summary['fes_rows']} FES rows; {summary['students_on_population']} students on population fallback"
    )
    print(f"Population weights: {summary['population_weights']}")
    return summary


def recalibrate_weights(
    uri: str | None = None,
    db_name: str | None = None,
    config_path: str | pathlib.Path | None = None,
) -> dict:
    """Nightly Eq. 2 recalibration — NON-DESTRUCTIVE.

    Recomputes the population and per-student weight vectors, upserts them
    into `fes_weights`, and refreshes the `fes` field of EXISTING
    `fes_history` rows in place from the sub-metrics already stored on them.

    Unlike `run_pipeline` this never issues a `delete_many`, so rows written
    concurrently by the live Celery session-end task survive, and no row is
    ever created or destroyed. Historical sub-metrics are untouched; only the
    composite (Eq. 1) and its weight vector are updated.
    """
    try:
        from pymongo import MongoClient
    except ImportError:
        print("pymongo is required: pip install pymongo")
        sys.exit(1)

    config = load_config(config_path)
    client = MongoClient(uri or os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client[db_name or os.getenv("MONGO_DB_NAME", "careermind")]

    by_student = _load_session_groups(db)
    student_metrics, all_pairs = _pass_submetrics(by_student, config)
    fes_weight_rows, population_weights, students_on_population = _pass_weights(
        student_metrics, all_pairs, config
    )

    for row in fes_weight_rows:
        db.fes_weights.update_one({"student": row["student"]}, {"$set": row}, upsert=True)

    weights_by_student = {row["student"]: row["weights"] for row in fes_weight_rows}
    projection = {"student": 1, **{m: 1 for m in SUBMETRICS}}
    refreshed = 0
    skipped = 0
    for doc in db.fes_history.find({}, projection):
        weights = weights_by_student.get(doc.get("student"), population_weights)
        metrics = {m: doc.get(m) for m in SUBMETRICS}
        fes = compute_fes(metrics, weights)
        if fes is None:
            skipped += 1
            continue
        db.fes_history.update_one(
            {"_id": doc["_id"]}, {"$set": {"fes": fes, "weights": weights}}
        )
        refreshed += 1

    summary = {
        "students": len(by_student),
        "sessions": sum(len(v) for v in by_student.values()),
        "weights_upserted": len(fes_weight_rows),
        "fes_rows_refreshed": refreshed,
        "fes_rows_skipped": skipped,
        "students_on_population": students_on_population,
        "population_weights": {k: round(v, 4) for k, v in population_weights.items()},
    }
    print(
        f"FES recalibration: {summary['weights_upserted']} weight rows upserted, "
        f"{refreshed} FES rows refreshed in place ({skipped} skipped), "
        f"{students_on_population} students on population fallback"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the FES batch pipeline")
    parser.add_argument("--uri", default=os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    parser.add_argument("--db", default=os.getenv("MONGO_DB_NAME", "careermind"))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    args = parser.parse_args()
    run_pipeline(args.uri, args.db, args.config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
