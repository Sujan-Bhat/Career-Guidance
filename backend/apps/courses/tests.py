"""Quiz attempt tests (Phase 3, FR04): counters + re-attempt detection."""


def test_quiz_attempt_updates_session_counters(registered):
    client, _ = registered
    from .models import Quiz

    quiz = Quiz(course="CS201", skill="dsa", title="DSA basics", questions=[]).save()
    session_id = client.post("/api/v1/collector/sessions/start").data["session_id"]

    first = client.post(
        f"/api/v1/courses/quizzes/{quiz.pk}/attempt",
        {"item_id": "q1", "correct": False},
        format="json",
    )
    assert first.status_code == 201
    assert first.data["is_reattempt"] is False

    second = client.post(
        f"/api/v1/courses/quizzes/{quiz.pk}/attempt",
        {"item_id": "q1", "correct": True},
        format="json",
    )
    assert second.status_code == 201
    assert second.data["is_reattempt"] is True  # previously incorrect -> re-attempt

    from apps.collector.models import BehaviourSession

    session = BehaviourSession.objects(pk=session_id).first()
    assert session.quiz_items == 2
    assert session.quiz_items_correct == 1
    assert session.quiz_reattempts == 1


def test_quiz_attempt_requires_active_session(registered):
    client, _ = registered
    from .models import Quiz

    quiz = Quiz(course="CS201", skill="dsa", title="DSA basics", questions=[]).save()
    response = client.post(
        f"/api/v1/courses/quizzes/{quiz.pk}/attempt",
        {"item_id": "q1", "correct": True},
        format="json",
    )
    assert response.status_code == 400


def test_quiz_attempt_requires_auth(api):
    response = api.post(
        "/api/v1/courses/quizzes/anything/attempt",
        {"item_id": "q1", "correct": True},
        format="json",
    )
    assert response.status_code in (401, 403)
