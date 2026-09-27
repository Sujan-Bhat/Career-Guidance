"""Sensitivity analysis of unvalidated design thresholds (paper Sec. VII #4, VIII).

Parameters to sweep:
  * stage1_eligibility_threshold      (default 0.60)      -> cascade P@10/R@10/nDCG@10
  * engagement_signal.min_session_minutes (default 15)    -> E flip-rate vs default
  * engagement_signal.min_interactions_per_min (default 3)  (same family)
  * engagement_signal.min_quiz_attempt_rate (default 0.6)   (same family)
  * weight_calibration.min_sessions (default 8)           -> per-student share + |ΔFES|
  * weight_calibration.min_graded_outcomes (default 2)      (same family)
  * weight_calibration.min_nonmissing_per_submetric (default 3) (same family)
  * reward_weights (Eq. 3 alpha/beta/gamma/delta dicts)   -> short-training mean reward

`sweep(parameter, values, run=None)` records metric deltas per value:
`{value: {metric: score}}`. Custom `run` callbacks make the core sweep
unit-testable without Mongo.
"""
import json
import os
from functools import lru_cache

DEFAULTS = {
    "stage1_eligibility_threshold": 0.60,
    "min_session_minutes": 15,
    "min_interactions_per_min": 3,
    "min_quiz_attempt_rate": 0.6,
    "min_sessions": 8,
    "min_graded_outcomes": 2,
    "min_nonmissing_per_submetric": 3,
}

FAMILY = {
    "stage1_eligibility_threshold": "stage1",
    "min_session_minutes": "engagement",
    "min_interactions_per_min": "engagement",
    "min_quiz_attempt_rate": "engagement",
    "min_sessions": "calibration",
    "min_graded_outcomes": "calibration",
    "min_nonmissing_per_submetric": "calibration",
    "reward_weights": "reward",
}

_ENGAGEMENT_PARAM = {
    "min_session_minutes": "min_session_minutes",
    "min_interactions_per_min": "min_interactions_per_min",
    "min_quiz_attempt_rate": "min_quiz_attempt_rate",
}
_CALIBRATION_PARAM = {
    "min_sessions": "min_sessions",
    "min_graded_outcomes": "min_graded_outcomes",
    "min_nonmissing_per_submetric": "min_nonmissing_per_submetric",
}


def sweep(parameter: str, values: list, run=None) -> dict:
    """Re-run the relevant pipeline component across `values`, record metric
    deltas, return {value: {metric: score}}."""
    if parameter not in FAMILY:
        raise ValueError(
            f"Unknown parameter {parameter!r}. Expected one of {sorted(FAMILY)}"
        )
    runner = run or _default_runner(parameter)
    results = {}
    for value in values:
        key = value if isinstance(value, (int, float, str, bool)) else json.dumps(value, sort_keys=True)
        results[key] = runner(value)
    return results


def _default_runner(parameter: str):
    family = FAMILY[parameter]
    if family == "stage1":
        return _run_stage1
    if family == "engagement":
        return lambda value: _run_engagement(parameter, value)
    if family == "calibration":
        return lambda value: _run_calibration(parameter, value)
    return _run_reward_weights


# ------------------------------------------------------------------ context

@lru_cache(maxsize=1)
def _mongo_db():
    from pymongo import MongoClient

    return MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))[
        os.getenv("MONGO_DB_NAME", "careermind")
    ]


@lru_cache(maxsize=1)
def _benchmark_context():
    from benchmark import build_context

    return build_context()


# ------------------------------------------------------------------ runners

def _run_stage1(threshold: float) -> dict:
    from benchmark import run_benchmark

    result = run_benchmark(_benchmark_context(), threshold=float(threshold))
    return dict(result["metrics"]["cascade"])


def _run_engagement(parameter: str, value: float) -> dict:
    """Flip-rate of the binary EngagementSignal vs the paper default."""
    from careermind_ml.fes.engagement import engagement_signal

    sessions = list(
        _mongo_db().sessions.find(
            {}, {"duration_minutes": 1, "interaction_count": 1, "quiz_items": 1}
        )
    )
    default_kw = {k: DEFAULTS[k] for k in _ENGAGEMENT_PARAM}
    variant_kw = {**default_kw, _ENGAGEMENT_PARAM[parameter]: value}

    flips = 0
    positive = 0
    total = 0
    for s in sessions:
        duration = float(s.get("duration_minutes") or 0.0)
        interactions = int(s.get("interaction_count") or 0)
        quiz_rate = min(1.0, (s.get("quiz_items") or 0) / 5.0)
        rate = (interactions / duration) if duration > 0 else 0.0
        base = engagement_signal(duration, quiz_attempt_rate=quiz_rate, interaction_rate=rate)
        variant = engagement_signal(
            duration,
            quiz_attempt_rate=quiz_rate,
            interaction_rate=rate,
            **{k: v for k, v in variant_kw.items()},
        )
        flips += int(base != variant)
        positive += variant
        total += 1
    return {
        "flip_rate": flips / total if total else 0.0,
        "positive_rate": positive / total if total else 0.0,
        "n_sessions": total,
    }


def _run_calibration(parameter: str, value: float) -> dict:
    """Gated per-student weight calibration: share of students getting a
    per-student vector + mean |ΔFES| vs the stored (default-gate) rows."""
    from careermind_ml.fes.weights import SUBMETRICS, calibrate_student_weights, compute_fes

    db = _mongo_db()
    rows = list(
        db.fes_history.find(
            {},
            {"session": 1, "student": 1, "fes": 1, "weights": 1,
             "tcr": 1, "sci": 1, "dfet": 1, "qap": 1, "lrds": 1},
        )
    )
    # FES rows are keyed f"{student}:{session_index}" (pipeline convention)
    outcomes = {
        f"{s.get('student')}:{s.get('session_index')}": s.get("assessment_score")
        for s in db.sessions.find({}, {"student": 1, "session_index": 1, "assessment_score": 1})
    }

    pairs_by_student: dict[str, list[dict]] = {}
    for row in rows:
        pair = {m: row.get(m) for m in SUBMETRICS}
        pair["outcome"] = outcomes.get(row["session"])
        pairs_by_student.setdefault(row["student"], []).append(pair)

    config = {**DEFAULTS}  # defaults for every gate
    config[_CALIBRATION_PARAM[parameter]] = value

    variant_weights: dict[str, dict | None] = {}
    per_student = 0
    for student, pairs in pairs_by_student.items():
        weights = calibrate_student_weights(pairs, config)
        variant_weights[student] = weights
        per_student += int(weights is not None)

    deltas = []
    for row in rows:
        metrics = {m: row.get(m) for m in SUBMETRICS}
        default_fes = row.get("fes")
        variant = variant_weights.get(row["student"])
        if default_fes is None:
            continue
        recomputed = compute_fes(metrics, variant) if variant else default_fes
        if recomputed is None:
            continue
        deltas.append(abs(recomputed - default_fes))

    n_students = len(pairs_by_student)
    return {
        "per_student_share": per_student / n_students if n_students else 0.0,
        "mean_abs_fes_delta": sum(deltas) / len(deltas) if deltas else 0.0,
        "n_students": n_students,
    }


def _run_reward_weights(weights: dict) -> dict:
    """Short fixed-seed DQN runs under each Eq. 3 weight vector — policy
    quality (mean reward) sensitivity without a full retrain."""
    import sys
    import pathlib

    import numpy as np
    import yaml

    from careermind_ml.rl.dqn import DQNAgent
    from careermind_ml.rl.environment import CareerGuidanceEnv
    from careermind_ml.rl.train import train_dqn

    root = pathlib.Path(__file__).resolve().parent.parent
    with open(root / "ml" / "configs" / "dqn.yaml") as fh:
        config = yaml.safe_load(fh)
    sys.path.insert(0, str(root / "data" / "simulator"))
    from simulator import StudentSimulator

    config.update(
        reward_weights=weights,
        max_episodes=30,
        steps_per_episode=40,
        log_every=0,
        random_state=7,
        artifact_path=str(root / "ml" / "artifacts" / "_sensitivity_dqn.pt"),
    )
    env = CareerGuidanceEnv(StudentSimulator(seed=config["random_state"]), config)
    metrics = train_dqn(env, DQNAgent(config), config)
    return {"mean_reward_last50": round(metrics["mean_reward_last50"], 4)}


def default_grids() -> dict:
    """Standard sweep grids for the pilot study (paper Sec. VIII #4)."""
    default_weights = {"alpha": 0.4, "beta": 0.3, "gamma": 0.1, "delta": 0.2}
    return {
        "stage1_eligibility_threshold": [0.40, 0.50, 0.60, 0.70, 0.80],
        "min_session_minutes": [10, 15, 20, 25],
        "min_interactions_per_min": [1.5, 2.0, 2.5, 3.0, 4.0],
        "min_sessions": [4, 6, 8, 12],
        "reward_weights": [
            default_weights,
            {**default_weights, "alpha": 0.7, "beta": 0.1, "gamma": 0.1, "delta": 0.1},
            {**default_weights, "alpha": 0.2, "beta": 0.2, "gamma": 0.4, "delta": 0.2},
            {**default_weights, "alpha": 0.2, "beta": 0.1, "gamma": 0.1, "delta": 0.6},
        ],
    }
