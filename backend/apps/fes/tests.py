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


def test_session_without_session_local_signals_is_skipped():
    """A session carrying no task/resource/quiz signal (phantom StrictMode
    close, page_view-only browse) must NOT produce a FESScore row: Eq. 1
    would collapse onto SCI alone (FES == SCI) and that row would shadow
    real readings as the dashboard's "latest", showing dashes for every
    other sub-metric."""
    from apps.accounts.models import StudentProfile
    from apps.collector.models import BehaviourEvent, BehaviourSession
    from apps.fes.models import FESScore
    from apps.fes.tasks import compute_session_fes

    profile = StudentProfile(
        email="skip@test.local",
        full_name="Skip Student",
        password_hash="x",
        source="careermind",
    ).save()

    # an earlier real session so the SCI window has >= 2 sessions
    earlier = datetime.utcnow() - timedelta(minutes=20)
    BehaviourSession(
        student=profile.student_id,
        status="completed",
        source="collector",
        started_at=earlier,
        ended_at=earlier + timedelta(minutes=5),
        duration_minutes=5.0,
        login_minute_of_day=earlier.hour * 60 + earlier.minute,
        date=earlier.date().isoformat(),
    ).save()

    base = datetime.utcnow() - timedelta(minutes=5)
    session = BehaviourSession(
        student=profile.student_id,
        status="active",
        started_at=base,
        source="collector",
    ).save()
    BehaviourEvent.objects.insert(
        [
            BehaviourEvent(
                session=str(session.pk),
                student=profile.student_id,
                type="page_view",
                timestamp=base + timedelta(minutes=1),
            )
        ]
    )

    result = compute_session_fes(str(session.pk))
    assert result["status"] == "skipped_no_signals"
    # SCI was computable — the skip is driven by the session-local four
    assert result["metrics"]["sci"] is not None
    for metric in ("tcr", "dfet", "qap", "lrds"):
        assert result["metrics"][metric] is None
    assert FESScore.objects(session=f"{profile.student_id}:{session.pk}").count() == 0


def test_sci_window_excludes_sub_minute_sessions():
    """Sub-second phantom sessions (StrictMode double-mount closes) must stay
    out of the SCI window: their ~0 durations explode CV(duration) and drag
    SCI toward its floor."""
    from apps.accounts.models import StudentProfile
    from apps.collector.models import BehaviourSession
    from apps.fes.tasks import _sci_window_sessions

    profile = StudentProfile(
        email="window@test.local",
        full_name="Window Student",
        password_hash="x",
        source="careermind",
    ).save()

    now = datetime.utcnow().replace(microsecond=0)
    phantom = BehaviourSession(
        student=profile.student_id,
        status="completed",
        source="collector",
        started_at=now - timedelta(minutes=3),
        ended_at=now - timedelta(minutes=3) + timedelta(seconds=1),
        duration_minutes=0.003,
        login_minute_of_day=600,
        date=now.date().isoformat(),
    ).save()
    real = BehaviourSession(
        student=profile.student_id,
        status="completed",
        source="collector",
        started_at=now - timedelta(minutes=10),
        ended_at=now - timedelta(minutes=2),
        duration_minutes=8.0,
        login_minute_of_day=610,
        date=now.date().isoformat(),
    ).save()
    target = BehaviourSession(
        student=profile.student_id,
        status="active",
        started_at=now,
        source="collector",
    ).save()

    window = _sci_window_sessions(profile.student_id, target)
    assert [s.pk for s in window] == [real.pk]
    assert phantom.pk not in [s.pk for s in window]


def test_fes_endpoints_fall_back_past_signal_less_rows(registered):
    """Legacy signal-less rows (written before the skip guard) must never
    shadow a real reading: /fes/current and the trend serve the newest row
    WITH signal, and /fes/submetrics serves each metric's most recent
    non-null value with its as-of timestamp."""
    from apps.fes.models import FESScore

    client, user = registered
    student = user["student_id"]
    weights = {"tcr": 0.2, "sci": 0.2, "dfet": 0.2, "qap": 0.2, "lrds": 0.2}

    rich_at = (datetime.utcnow() - timedelta(hours=2)).replace(microsecond=0)
    FESScore(
        session=f"{student}:rich",
        student=student,
        tcr=0.5,
        sci=0.6,
        dfet=0.4,
        qap=0.3,
        lrds=0.2,
        fes=0.45,
        weights=weights,
        computed_at=rich_at,
    ).save()

    degenerate_at = datetime.utcnow().replace(microsecond=0)
    FESScore(
        session=f"{student}:phantom",
        student=student,
        tcr=None,
        sci=0.3,
        dfet=None,
        qap=None,
        lrds=None,
        fes=0.3,
        weights=weights,
        computed_at=degenerate_at,
    ).save()

    current = client.get("/api/v1/fes/current")
    assert current.status_code == 200
    assert current.data["fes"] == 0.45  # skips the degenerate newest row
    assert current.data["tcr"] == 0.5

    sub = client.get("/api/v1/fes/submetrics")
    assert sub.status_code == 200
    assert sub.data["submetrics"]["tcr"] == {"value": 0.5, "as_of": rich_at}
    assert sub.data["submetrics"]["sci"] == {"value": 0.3, "as_of": degenerate_at}
    assert sub.data["latest"]["computed_at"] == degenerate_at
    assert "tcr" in sub.data["latest"]["missing"]
    assert sub.data["student_weights"] == weights

    history = client.get("/api/v1/fes/history")
    assert history.status_code == 200
    assert history.data["count"] == 1  # degenerate row excluded from the trend


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


def test_history_rows_carry_sub_metrics_for_the_metrics_page(registered):
    """The metrics page charts the sub-metric history straight from the DB, so
    /fes/history must serve each row's five sub-metrics (null where that session
    recorded no such activity), the composite, and the weight vector applied --
    not just the composite the 14-day trend stuck with."""
    from apps.fes.models import FESScore

    client, user = registered
    student = user["student_id"]
    weights = {"tcr": 0.4, "sci": 0.1, "dfet": 0.2, "qap": 0.2, "lrds": 0.1}
    first = (datetime.utcnow() - timedelta(hours=3)).replace(microsecond=0)
    second = (datetime.utcnow() - timedelta(hours=1)).replace(microsecond=0)

    FESScore(
        session=f"{student}:metrics1",
        student=student,
        tcr=0.5,
        sci=0.6,
        dfet=0.4,
        qap=None,  # no quiz that session
        lrds=0.2,
        fes=0.45,
        weights=weights,
        computed_at=first,
    ).save()
    FESScore(
        session=f"{student}:metrics2",
        student=student,
        tcr=0.8,
        sci=0.7,
        dfet=0.6,
        qap=0.3,
        lrds=0.5,
        fes=0.68,
        weights=weights,
        computed_at=second,
    ).save()

    response = client.get("/api/v1/fes/history")
    assert response.status_code == 200
    rows = response.data["history"]
    assert [r["fes"] for r in rows] == [0.45, 0.68]  # chronological
    assert rows[0]["qap"] is None  # a missing metric is a gap, never a zero
    assert rows[1]["qap"] == 0.3
    assert rows[1]["tcr"] == 0.8
    assert rows[1]["weights"] == weights
    assert rows[1]["session"].endswith(":metrics2")


def test_history_limit_is_capped_and_keeps_the_newest_rows(registered):
    """`limit` must clamp at 200 and keep the NEWEST rows (the old ascending
    sort + limit returned the oldest ones)."""
    from apps.fes.models import FESScore

    client, user = registered
    student = user["student_id"]
    weights = {"tcr": 0.2, "sci": 0.2, "dfet": 0.2, "qap": 0.2, "lrds": 0.2}
    for index in range(3):
        FESScore(
            session=f"{student}:limit{index}",
            student=student,
            tcr=0.1 * index,
            sci=0.5,
            dfet=0.5,
            qap=None,
            lrds=0.5,
            fes=0.3 + 0.05 * index,
            weights=weights,
            computed_at=(datetime.utcnow() - timedelta(hours=3 - index)).replace(microsecond=0),
        ).save()

    two = client.get("/api/v1/fes/history?limit=2")
    assert two.data["count"] == 2
    assert [r["fes"] for r in two.data["history"]] == [0.35, 0.40]  # newest two, oldest->newest

    assert client.get("/api/v1/fes/history?limit=9999").data["count"] == 3
    assert client.get("/api/v1/fes/history?limit=nonsense").data["count"] == 3
