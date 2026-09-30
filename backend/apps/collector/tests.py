"""Collector tests (Phase 3): session lifecycle, event ingestion, session-end FES."""
from datetime import datetime, timedelta

import pytest


def test_session_start_creates_active_session(registered):
    client, user = registered
    response = client.post("/api/v1/collector/sessions/start")
    assert response.status_code == 201
    assert response.data["session_id"]

    from apps.collector.models import BehaviourSession

    session = BehaviourSession.objects(pk=response.data["session_id"]).first()
    assert session is not None
    assert session.status == "active"
    assert session.source == "collector"
    assert session.student == user["student_id"]


def test_events_require_active_session(registered):
    client, _ = registered
    response = client.post(
        "/api/v1/collector/events/batch",
        {"events": [{"type": "page_view", "timestamp": datetime.utcnow().isoformat()}]},
        format="json",
    )
    assert response.status_code == 400


def test_event_batch_ingestion_and_end_to_end_fes(registered):
    client, user = registered
    started = client.post("/api/v1/collector/sessions/start").data

    # events must fall AFTER the session start (server timestamps started_at)
    base = datetime.utcnow() + timedelta(seconds=1)
    events = [{"type": "page_view", "timestamp": base.isoformat()}]
    events += [
        {"type": "task_start", "timestamp": (base + timedelta(minutes=2)).isoformat()},
        {"type": "task_complete", "timestamp": (base + timedelta(minutes=5)).isoformat()},
        {
            "type": "resource_open",
            "resource_id": "r1",
            "metadata": {"resource_type": "video"},
            "timestamp": (base + timedelta(minutes=6)).isoformat(),
        },
        {
            "type": "resource_close",
            "resource_id": "r1",
            "metadata": {"resource_type": "video"},
            "timestamp": (base + timedelta(minutes=12)).isoformat(),
        },
    ]
    response = client.post(
        "/api/v1/collector/events/batch",
        {"session_id": started["session_id"], "events": events},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["stored"] == len(events)

    end = client.post(f"/api/v1/collector/sessions/{started['session_id']}/end")
    assert end.status_code == 200
    assert end.data["fes_queued"] is True  # eager Celery ran the task synchronously

    from apps.fes.models import FESScore

    row = FESScore.objects(session=f"{user['student_id']}:{started['session_id']}").first()
    assert row is not None, "session-end FES task must write a FESScore row"
    assert 0.0 <= row.fes <= 1.0
    assert row.tcr == 1.0
    assert row.lrds is not None  # 6-min video dwell > 300s threshold
    assert row.dfet is not None  # sustained engagement present

    # /fes/current with JWT resolves to THIS student
    current = client.get("/api/v1/fes/current")
    assert current.status_code == 200
    assert current.data["student"] == user["student_id"]


def test_session_end_is_idempotent(registered):
    client, _ = registered
    session_id = client.post("/api/v1/collector/sessions/start").data["session_id"]
    assert client.post(f"/api/v1/collector/sessions/{session_id}/end").status_code == 200
    assert client.post(f"/api/v1/collector/sessions/{session_id}/end").status_code == 409


def test_idle_gap_never_exceeds_dwell(registered):
    """idle_start fired BEFORE the resource was opened must not leak into the
    visit: the gap would otherwise be measured from before `open_at`, making
    idle_gap_seconds > dwell_seconds and corrupting the DFET heuristic."""
    client, _ = registered
    session_id = client.post("/api/v1/collector/sessions/start").data["session_id"]

    base = datetime.utcnow() + timedelta(seconds=1)
    events = [
        # idle while NO visit is open (10 minutes before the resource opens)
        {"type": "idle_start", "timestamp": base.isoformat()},
        {
            "type": "resource_open",
            "resource_id": "r1",
            "metadata": {"resource_type": "article"},
            "timestamp": (base + timedelta(minutes=10)).isoformat(),
        },
        {
            "type": "resource_close",
            "resource_id": "r1",
            "metadata": {"resource_type": "article"},
            "timestamp": (base + timedelta(minutes=11)).isoformat(),
        },
        # and a normal in-visit idle interval for contrast
        {
            "type": "resource_open",
            "resource_id": "r2",
            "metadata": {"resource_type": "article"},
            "timestamp": (base + timedelta(minutes=12)).isoformat(),
        },
        {"type": "idle_start", "timestamp": (base + timedelta(minutes=13)).isoformat()},
        {"type": "idle_end", "timestamp": (base + timedelta(minutes=14)).isoformat()},
        {
            "type": "resource_close",
            "resource_id": "r2",
            "metadata": {"resource_type": "article"},
            "timestamp": (base + timedelta(minutes=15)).isoformat(),
        },
    ]
    assert client.post(
        "/api/v1/collector/events/batch",
        {"session_id": session_id, "events": events},
        format="json",
    ).status_code == 200

    from apps.collector.models import BehaviourSession
    from apps.collector.services import recompute_session_aggregates

    session = BehaviourSession.objects(pk=session_id).first()
    session.started_at = base
    session.ended_at = base + timedelta(minutes=16)
    recompute_session_aggregates(session)

    session.reload()
    assert len(session.resource_visits) == 2
    first, second = session.resource_visits
    # pre-visit idle is discarded entirely
    assert first["idle_gap_seconds"] == 0.0
    # in-visit idle (1 min of a 3 min dwell) is kept
    assert second["idle_gap_seconds"] == pytest.approx(60.0)
    for visit in session.resource_visits:
        assert visit["idle_gap_seconds"] <= visit["dwell_seconds"]
