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


def test_session_end_task_reads_the_fes_yaml():
    """tasks.CONFIG must come from ml/configs/fes.yaml, not the code defaults
    `load_config(None)` used to return — otherwise tuning the YAML silently
    desynchronises the live session-end task from `make train-fes`."""
    from careermind_ml.fes.pipeline import DEFAULT_CONFIG_PATH, load_config

    from apps.fes import tasks

    assert DEFAULT_CONFIG_PATH.is_file()
    expected = load_config(DEFAULT_CONFIG_PATH)
    assert tasks.CONFIG == expected
    # and the YAML's own values actually flow through (not just the defaults)
    assert expected["sci_window_days"] == 14
    assert expected["weight_calibration"]["min_sessions"] == 8
    assert expected["weight_calibration"]["min_graded_outcomes"] == 2
    assert expected["weight_calibration"]["min_nonmissing_per_submetric"] == 3


def test_load_config_honours_a_custom_path(tmp_path):
    from careermind_ml.fes.pipeline import load_config

    cfg = tmp_path / "fes.yaml"
    cfg.write_text("sci_window_days: 7\nweight_calibration:\n  min_sessions: 5\n")
    loaded = load_config(cfg)
    assert loaded["sci_window_days"] == 7
    assert loaded["weight_calibration"]["min_sessions"] == 5
    # untouched keys fall back to the documented defaults
    assert loaded["weight_calibration"]["min_graded_outcomes"] == 2


def test_recalibration_task_is_scheduled():
    """The nightly job must actually be wired: CELERY_BEAT_SCHEDULE in
    settings + the task name registered by @shared_task."""
    from django.conf import settings

    from apps.fes.tasks import recompute_all_weights

    schedule = settings.CELERY_BEAT_SCHEDULE
    assert "fes.recompute-all-weights" in schedule
    entry = schedule["fes.recompute-all-weights"]
    assert entry["task"] == "fes.recompute_all_weights"
    assert recompute_all_weights.name == "fes.recompute_all_weights"


def test_recompute_all_weights_is_non_destructive(monkeypatch):
    """The beat job upserts weights and refreshes fes_history rows in place;
    it must never issue a delete_many (that is run_pipeline's contract)."""
    import pymongo

    import careermind_ml.fes.pipeline as pipeline

    calls = {"delete_many": 0, "upserts": 0}

    class _FakeHistory:
        def find(self, *_a, **_k):
            return iter(())

        def delete_many(self, *_a, **_k):
            calls["delete_many"] += 1

    class _FakeWeights:
        def update_one(self, *_a, **_k):
            calls["upserts"] += 1

        def delete_many(self, *_a, **_k):
            calls["delete_many"] += 1

    class _FakeDB:
        fes_history = _FakeHistory()
        fes_weights = _FakeWeights()

    class _FakeClient:
        def __init__(self, *_a, **_k):
            pass

        def __getitem__(self, _name):
            return _FakeDB()

    monkeypatch.setattr(pymongo, "MongoClient", _FakeClient)
    monkeypatch.setattr(pipeline, "_load_session_groups", lambda db: {})

    summary = pipeline.recalibrate_weights(config_path=pipeline.DEFAULT_CONFIG_PATH)
    assert summary["weights_upserted"] == 1  # the population row only
    assert calls["upserts"] == 1
    assert calls["delete_many"] == 0
