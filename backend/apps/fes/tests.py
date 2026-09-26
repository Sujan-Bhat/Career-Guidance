"""FES task tests (Phase 3): compute_session_fes on a manual collector session."""
from datetime import datetime, timedelta


def test_compute_session_fes_on_manual_session():
    from apps.collector.models import BehaviourEvent, BehaviourSession
    from apps.fes.tasks import compute_session_fes
    from apps.accounts.models import StudentProfile

    profile = StudentProfile(
        email="manual@test.local",
        full_name="Manual Student",
        password_hash="x",
        source="careermind",
    ).save()

    base = datetime.utcnow() - timedelta(minutes=25)
    session = BehaviourSession(
        student=profile.student_id,
        status="active",
        started_at=base,
        source="collector",
    ).save()

    BehaviourEvent.objects.insert(
        [
            BehaviourEvent(session=str(session.pk), student=profile.student_id, type="page_view", timestamp=base),
            BehaviourEvent(session=str(session.pk), student=profile.student_id, type="task_start", timestamp=base + timedelta(minutes=1)),
            BehaviourEvent(session=str(session.pk), student=profile.student_id, type="task_complete", timestamp=base + timedelta(minutes=3)),
            BehaviourEvent(session=str(session.pk), student=profile.student_id, type="resource_open", metadata={"resource_type": "article"}, timestamp=base + timedelta(minutes=4)),
            BehaviourEvent(session=str(session.pk), student=profile.student_id, type="resource_close", metadata={"resource_type": "article"}, timestamp=base + timedelta(minutes=10)),
        ]
    )

    result = compute_session_fes(str(session.pk))
    assert result["status"] == "ok"
    assert 0.0 <= result["fes"] <= 1.0
    assert result["metrics"]["tcr"] == 1.0
    # 6-min article dwell > 180s threshold -> LRDS = 1.0
    assert result["metrics"]["lrds"] == 1.0


def test_weights_fallback_to_uniform_without_calibration():
    from apps.fes.tasks import _weights_for
    from careermind_ml.fes.weights import SUBMETRICS

    weights = _weights_for("no-such-student")
    assert set(weights) == set(SUBMETRICS)
    assert abs(sum(weights.values()) - 1.0) < 1e-9
