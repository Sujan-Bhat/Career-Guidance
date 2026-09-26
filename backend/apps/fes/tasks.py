"""Session-end FES computation task (paper Sec. V-A; FR03).

On session end (apps.collector SessionEndView), computes the five
sub-metrics for that single session, applies the student's Eq. 2 weights
(population fallback below the calibration gates), and persists one FESScore
row. Weight recalibration itself is a batch operation (`make train-fes` /
nightly beat job) per the batch-recompute design decision.
"""
from datetime import datetime, timedelta

from celery import shared_task

from careermind_ml.fes.pipeline import load_config
from careermind_ml.fes.submetrics import (
    distraction_free_engagement_time,
    learning_resource_depth_score,
    quiz_attempt_persistence,
    session_consistency_index,
    task_completion_rate,
)
from careermind_ml.fes.weights import SUBMETRICS, compute_fes

from ..collector.models import BehaviourSession
from ..collector.services import recompute_session_aggregates
from .models import FESScore, FESWeights

CONFIG = load_config(None)


def _weights_for(student_id: str) -> dict:
    weights = FESWeights.objects(student=student_id).first()
    if weights is None:
        weights = FESWeights.objects(student=None).first()  # population cold-start
    if weights is None:
        return {m: 1.0 / len(SUBMETRICS) for m in SUBMETRICS}  # uniform last resort
    return weights.weights


@shared_task(name="fes.compute_session_fes")
def compute_session_fes(session_id: str) -> dict:
    session = BehaviourSession.objects(pk=session_id).first()
    if session is None:
        return {"status": "not_found", "session_id": session_id}

    if session.source == "collector":
        session = recompute_session_aggregates(session)  # raw events -> aggregates

    # SCI window: this student's sessions in the trailing 14 days
    window_start = session.started_at - timedelta(days=CONFIG["sci_window_days"])
    window = list(
        BehaviourSession.objects(
            student=session.student,
            started_at__gte=window_start,
            started_at__lte=session.started_at,
        ).order_by("started_at")
    )

    session_dict = session.to_mongo().to_dict()
    metrics = {
        "tcr": task_completion_rate(
            session_dict.get("tasks_started"), session_dict.get("tasks_completed")
        ),
        "sci": session_consistency_index(
            [s.login_minute_of_day for s in window if s.login_minute_of_day is not None],
            [s.duration_minutes for s in window if s.duration_minutes],
        ),
        "dfet": distraction_free_engagement_time(
            session_dict.get("resource_visits") or [], session_dict.get("duration_minutes")
        ),
        "qap": quiz_attempt_persistence(
            session_dict.get("quiz_items"),
            session_dict.get("quiz_items_correct"),
            session_dict.get("quiz_reattempts"),
        ),
        "lrds": learning_resource_depth_score(
            session_dict.get("resource_visits") or [], CONFIG["lrds_thresholds"]
        ),
    }
    weights = _weights_for(session.student)
    fes = compute_fes(metrics, weights)
    if fes is None:
        return {"status": "no_metrics", "session_id": session_id, "metrics": metrics}

    key = f"{session.student}:{session.pk}"
    FESScore.objects(session=key).delete()  # idempotent on recompute
    FESScore(
        session=key,
        student=session.student,
        **{m: metrics.get(m) for m in SUBMETRICS},
        fes=fes,
        weights=weights,
        computed_at=session.started_at,
    ).save()
    return {"status": "ok", "session_id": session_id, "fes": fes, "metrics": metrics}


@shared_task(name="fes.recompute_all_weights")
def recompute_all_weights() -> dict:
    """Nightly batch: re-run per-student Eq. 2 calibration (Phase 10 wires the
    beat schedule). Runs the ml package pipeline."""
    from careermind_ml.fes.pipeline import run_pipeline

    return run_pipeline()
