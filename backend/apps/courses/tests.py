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


# ---- Phase 8: catalogue + quiz listing/detail -----------------------------

def test_course_list_returns_catalogue_shape(api):
    response = api.get("/api/v1/courses/")
    assert response.status_code == 200
    assert response.data["count"] == len(response.data["courses"])
    if response.data["courses"]:
        course = response.data["courses"][0]
        assert {"code", "title", "difficulty", "skill_tags", "pathway"} <= set(course)


def test_quiz_list_is_public_and_hides_answers(api, registered):
    from .models import Quiz

    Quiz(
        skill="dsa",
        title="Public quiz",
        questions=[{"question": "Q?", "options": ["a", "b"], "answer": 1, "difficulty": 1}],
    ).save()

    response = api.get("/api/v1/courses/quizzes")
    assert response.status_code == 200
    listed = response.data["quizzes"][0]
    assert listed["quiz_id"]
    assert listed["item_count"] == 1
    assert "questions" not in listed  # answers must not leak in the list


def test_quiz_detail_requires_auth_and_returns_answers(api, registered):
    from .models import Quiz

    quiz = Quiz(
        skill="sql",
        title="Private quiz",
        questions=[{"question": "Q?", "options": ["a", "b"], "answer": 1, "difficulty": 1}],
    ).save()

    assert api.get(f"/api/v1/courses/quizzes/{quiz.pk}").status_code in (401, 403)

    client, _ = registered
    response = client.get(f"/api/v1/courses/quizzes/{quiz.pk}")
    assert response.status_code == 200
    assert response.data["questions"][0]["answer"] == 1  # taker sees answers (client scores)

    assert client.get("/api/v1/courses/quizzes/000000000000000000000000").status_code == 404
