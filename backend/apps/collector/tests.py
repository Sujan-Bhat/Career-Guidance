"""Collector tests (Phase 3): session lifecycle, event ingestion, session-end FES."""
from datetime import datetime, timedelta


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
