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
each run). Phase 3 adds the Celery session-end hook alongside it.

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
            [w.get("login_minute_of_day") for w in window],
            [w.get("duration_minutes") for w in window],
        )
    else:
        metrics["sci"] = None
    return metrics


def _session_datetime(session: dict) -> datetime:
    base = datetime.fromisoformat(session["date"])
    minute = session.get("login_minute_of_day", 0)
    return base + timedelta(minutes=int(minute))


def run_pipeline(
    uri: str | None = None,
    db_name: str | None = None,
    config_path: str | pathlib.Path | None = None,
) -> dict:
    """Execute the full FES batch pipeline; returns a summary dict."""
    try:
        from pymongo import MongoClient
    except ImportError:
        print("pymongo is required: pip install pymongo")
        sys.exit(1)

    config = load_config(config_path)
    client = MongoClient(uri or os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client[db_name or os.getenv("MONGO_DB_NAME", "careermind")]

    sessions = list(
        db.sessions.find({"source": {"$in": ["simulator", "collector"]}})
    )
    by_student: dict[str, list[dict]] = {}
    for session in sessions:
        by_student.setdefault(session["student"], []).append(session)

    # ---- pass 1: per-session sub-metrics (+ SCI window) and outcome pairs ----
    student_metrics: dict[str, list[tuple[dict, dict]]] = {}
    all_pairs: list[dict] = []
    for student, sess in by_student.items():
        sess.sort(key=lambda s: (s["date"], s.get("session_index", 0)))
        computed = []
        for i, session in enumerate(sess):
            session_date = datetime.fromisoformat(session["date"]).date()
            window = [
                w
                for w in sess[: i + 1]
                if (session_date - datetime.fromisoformat(w["date"]).date()).days
                <= config["sci_window_days"]
            ]
            metrics = compute_session_metrics(session, window, config)
            computed.append((session, metrics))
            all_pairs.append({**metrics, "outcome": session.get("assessment_score")})
        student_metrics[student] = computed

    # ---- pass 2: population weights, then per-student (gated) weights ----
    population_weights = calibrate_population_weights(all_pairs, config["weight_calibration"])

    fes_weight_rows = [
        {
            "student": None,  # population-level cold-start vector
            "weights": population_weights,
            "n_sessions": len(all_pairs),
            "n_graded_outcomes": len(all_pairs),
            "computed_at": datetime.utcnow(),
        }
    ]
    fes_rows = []
    students_on_population = 0
    for student, computed in student_metrics.items():
        pairs = [
            {**metrics, "outcome": session.get("assessment_score")} for session, metrics in computed
        ]
        weights = calibrate_student_weights(pairs, config["weight_calibration"])
        if weights is None:
            weights = population_weights
            students_on_population += 1
        fes_weight_rows.append(
            {
                "student": student,
                "weights": weights,
                "n_sessions": len(pairs),
                "n_graded_outcomes": sum(1 for p in pairs if p.get("outcome") is not None),
                "computed_at": datetime.utcnow(),
            }
        )
        for session, metrics in computed:
            fes = compute_fes(metrics, weights)
            if fes is None:
                continue
            fes_rows.append(
                {
                    "session": f"{student}:{session.get('session_index')}",
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
        "sessions": len(sessions),
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
