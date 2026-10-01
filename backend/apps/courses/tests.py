"""Quiz attempt tests (Phase 3, FR04): counters + re-attempt detection."""


def test_quiz_attempt_updates_session_counters(registered):
    client, _ = registered
    from .models import Quiz

    quiz = Quiz(
        course="CS201",
        skill="dsa",
        title="DSA basics",
        questions=[
            {"question": "Q1?", "options": ["a", "b", "c"], "answer": 1, "difficulty": 1},
            {"question": "Q2?", "options": ["x", "y"], "answer": 0, "difficulty": 1},
        ],
    ).save()
    session_id = client.post("/api/v1/collector/sessions/start").data["session_id"]

    first = client.post(
        f"/api/v1/courses/quizzes/{quiz.pk}/attempt",
        {"item_id": "q0", "selected": 0},  # wrong (answer is 1)
        format="json",
    )
    assert first.status_code == 201
    assert first.data["correct"] is False  # scored server-side
    assert first.data["is_reattempt"] is False

    second = client.post(
        f"/api/v1/courses/quizzes/{quiz.pk}/attempt",
        {"item_id": "q0", "selected": 1},  # right
        format="json",
    )
    assert second.status_code == 201
    assert second.data["correct"] is True
    assert second.data["is_reattempt"] is True  # previously incorrect -> re-attempt

    from apps.collector.models import BehaviourSession

    session = BehaviourSession.objects(pk=session_id).first()
    assert session.quiz_items == 2
    assert session.quiz_items_correct == 1
    assert session.quiz_reattempts == 1


def test_quiz_attempt_requires_active_session(registered):
    client, _ = registered
    from .models import Quiz

    quiz = Quiz(
        skill="dsa",
        title="No session",
        questions=[{"question": "Q?", "options": ["a", "b"], "answer": 1, "difficulty": 1}],
    ).save()
    response = client.post(
        f"/api/v1/courses/quizzes/{quiz.pk}/attempt",
        {"item_id": "q0", "selected": 1},
        format="json",
    )
    assert response.status_code == 400


def test_quiz_attempt_requires_auth(api):
    response = api.post(
        "/api/v1/courses/quizzes/anything/attempt",
        {"item_id": "q0", "selected": 1},
        format="json",
    )
    assert response.status_code in (401, 403)


# ---- Hardening: server-side scoring + item validation (security review) ----

def _seeded_quiz():
    from .models import Quiz

    return Quiz(
        skill="sec",
        title="Hardened quiz",
        questions=[
            {"question": "Q?", "options": ["a", "b", "c"], "answer": 1, "difficulty": 1},
            {"question": "Q2?", "options": ["x", "y"], "answer": 0, "difficulty": 1},
        ],
    ).save()


def test_quiz_attempt_scores_server_side(registered):
    """The client sends only its selection; `correct` comes from the stored
    answer, so a tampering client cannot declare wrong answers correct."""
    client, _ = registered
    quiz = _seeded_quiz()
    client.post("/api/v1/collector/sessions/start")

    honest = client.post(
        f"/api/v1/courses/quizzes/{quiz.pk}/attempt",
        {"item_id": "q0", "selected": 1},
        format="json",
    )
    assert honest.data["correct"] is True

    # no request field can flip the verdict for a wrong selection
    for payload in (
        {"item_id": "q0", "selected": 2, "correct": True},
        {"item_id": "q0", "selected": 0, "correct": 1},
    ):
        spoof = client.post(f"/api/v1/courses/quizzes/{quiz.pk}/attempt", payload, format="json")
        assert spoof.status_code == 201
        assert spoof.data["correct"] is False


def test_quiz_attempt_records_unanswered_selection(registered):
    """selected=-1 (no answer) still counts as an attempt, never correct."""
    client, _ = registered
    quiz = _seeded_quiz()
    client.post("/api/v1/collector/sessions/start")

    response = client.post(
        f"/api/v1/courses/quizzes/{quiz.pk}/attempt",
        {"item_id": "q1", "selected": -1},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["correct"] is False


def test_quiz_attempt_rejects_unknown_items(registered):
    """item_id must be an existing q<index> of THIS quiz: no phantom items,
    no out-of-range indices, no free-form strings in the attempt log."""
    client, _ = registered
    quiz = _seeded_quiz()
    client.post("/api/v1/collector/sessions/start")

    for item_id in ("item_does_not_exist", "q99", "q-1", "qq0", "q01x", "", "Q0"):
        response = client.post(
            f"/api/v1/courses/quizzes/{quiz.pk}/attempt",
            {"item_id": item_id, "selected": 1},
            format="json",
        )
        assert response.status_code == 400, item_id

    from .models import QuizAttempt

    assert QuizAttempt.objects(quiz=str(quiz.pk)).count() == 0


def test_quiz_attempt_rejects_wrong_payload_types(registered):
    """selected must be a real int in range; booleans, strings, floats and
    operator-style objects are rejected, not stored."""
    client, _ = registered
    quiz = _seeded_quiz()
    client.post("/api/v1/collector/sessions/start")

    for payload in (
        {"item_id": "q0", "selected": True},
        {"item_id": "q0", "selected": "1"},
        {"item_id": "q0", "selected": 1.5},
        {"item_id": "q0", "selected": {"$gt": ""}},
        {"item_id": "q0", "selected": [1]},
        {"item_id": "q0", "selected": 3},  # past the options list
        {"item_id": {"$gt": ""}, "selected": 1},
        {"selected": 1},  # missing item_id
    ):
        response = client.post(f"/api/v1/courses/quizzes/{quiz.pk}/attempt", payload, format="json")
        assert response.status_code == 400, payload

    from .models import QuizAttempt

    assert QuizAttempt.objects(quiz=str(quiz.pk)).count() == 0


def test_quiz_attempt_malformed_quiz_id_is_404(api, registered):
    """Regression: a non-ObjectId quiz id raised an unhandled ValidationError
    (500 + debug page); it must be a clean 404 on detail and attempt."""
    client, _ = registered
    assert api.get("/api/v1/courses/quizzes/NOT_AN_OID").status_code in (401, 403)  # auth first
    assert client.get("/api/v1/courses/quizzes/NOT_AN_OID").status_code == 404
    response = client.post(
        "/api/v1/courses/quizzes/NOT_AN_OID/attempt",
        {"item_id": "q0", "selected": 1},
        format="json",
    )
    assert response.status_code == 404


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
    assert client.get("/api/v1/courses/quizzes/also-not-an-oid").status_code == 404
