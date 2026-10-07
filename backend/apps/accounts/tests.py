"""Auth tests (Phase 3): register -> login -> me round trip, JWT guards."""
import time
from datetime import datetime, timezone

import pytest
from django.test import override_settings

from .models import StudentProfile

REGISTER = {
    "email": "student@test.local",
    "full_name": "Test Student",
    "password": "password123",
    "programme": "BE Computer Science",
}


def test_register_creates_profile_and_tokens(api):
    response = api.post("/api/v1/accounts/register", REGISTER, format="json")
    assert response.status_code == 201
    assert response.data["access"] and response.data["refresh"]
    profile = StudentProfile.objects(email=REGISTER["email"]).first()
    assert profile is not None
    assert profile.source == "careermind"
    assert profile.password_hash != REGISTER["password"]  # bcrypt-hashed


def test_duplicate_email_rejected(api):
    api.post("/api/v1/accounts/register", REGISTER, format="json")
    response = api.post("/api/v1/accounts/register", REGISTER, format="json")
    assert response.status_code == 400


def test_login_and_me_round_trip(api):
    api.post("/api/v1/accounts/register", REGISTER, format="json")
    login = api.post(
        "/api/v1/accounts/login",
        {"email": REGISTER["email"], "password": REGISTER["password"]},
        format="json",
    )
    assert login.status_code == 200
    assert login.data["access"]

    auth = api
    auth.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    me = auth.get("/api/v1/accounts/me")
    assert me.status_code == 200
    assert me.data["email"] == REGISTER["email"]
    assert me.data["full_name"] == "Test Student"


def test_wrong_password_rejected(api):
    api.post("/api/v1/accounts/register", REGISTER, format="json")
    response = api.post(
        "/api/v1/accounts/login",
        {"email": REGISTER["email"], "password": "wrong-password"},
        format="json",
    )
    assert response.status_code == 401


def test_me_requires_authentication(api):
    response = api.get("/api/v1/accounts/me")
    assert response.status_code in (401, 403)


def test_refresh_flow(api):
    registered = api.post("/api/v1/accounts/register", REGISTER, format="json")
    refresh = registered.data["refresh"]
    response = api.post("/api/v1/accounts/refresh", {"refresh": refresh}, format="json")
    assert response.status_code == 200
    assert response.data["access"]
    # refresh token must not be usable as an access token
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh}")
    assert api.get("/api/v1/accounts/me").status_code in (401, 403)


def test_short_password_rejected(api):
    payload = {**REGISTER, "email": "short@test.local", "password": "short"}
    assert api.post("/api/v1/accounts/register", payload, format="json").status_code == 400


def test_duplicate_email_race_returns_400(api, monkeypatch):
    """Two concurrent registers can both pass the pre-insert duplicate check;
    the unique index then raises NotUniqueError, which must map to the same
    400 the pre-check produces instead of an unhandled 500."""
    from mongoengine import NotUniqueError

    def boom(self, *args, **kwargs):
        raise NotUniqueError("email")

    monkeypatch.setattr(StudentProfile, "save", boom)
    response = api.post("/api/v1/accounts/register", REGISTER, format="json")
    assert response.status_code == 400
    assert response.data["detail"] == "Email already registered"


def test_database_errors_are_not_masked_as_auth_failures(monkeypatch):
    """`except (DoesNotExist, Exception)` used to swallow Mongo outages and
    relabel them "Profile not found" (401). Only DoesNotExist is an auth
    failure; anything else must propagate."""
    from apps.accounts.auth import CareermindJWTAuthentication, mint_tokens

    token = mint_tokens("64b000000000000000000000")["access"]

    class _BrokenManager:
        def get(self, **kwargs):
            raise RuntimeError("mongo is down")

    monkeypatch.setattr(StudentProfile, "objects", _BrokenManager())

    class _Request:
        META = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    with pytest.raises(RuntimeError, match="mongo is down"):
        CareermindJWTAuthentication().authenticate(_Request())


def test_unknown_subject_is_still_an_auth_failure(api):
    from apps.accounts.auth import mint_tokens

    token = mint_tokens("64b0000000000000000000ff")["access"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    response = api.get("/api/v1/accounts/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Password hardening: SHA-256 pre-hash before bcrypt (72-byte truncation fix)
# ---------------------------------------------------------------------------

LONG_A = "K" * 80  # 80 bytes — past bcrypt's 72-byte silent truncation
LONG_B = "K" * 72 + "different-suffix"  # identical first 72 bytes to LONG_A


def test_long_password_round_trip(api):
    """>72-byte passwords keep full entropy: register + login round trip."""
    payload = {**REGISTER, "email": "long@test.local", "password": LONG_A}
    assert api.post("/api/v1/accounts/register", payload, format="json").status_code == 201
    login = api.post(
        "/api/v1/accounts/login",
        {"email": "long@test.local", "password": LONG_A},
        format="json",
    )
    assert login.status_code == 200
    assert login.data["access"]


def test_long_passwords_sharing_72_byte_prefix_are_distinct(api):
    """Regression: raw bcrypt truncated at 72 bytes, so LONG_B authenticated
    against LONG_A's account. The SHA-256 pre-hash makes them distinct."""
    payload = {**REGISTER, "email": "prefix@test.local", "password": LONG_A}
    api.post("/api/v1/accounts/register", payload, format="json")
    response = api.post(
        "/api/v1/accounts/login",
        {"email": "prefix@test.local", "password": LONG_B},
        format="json",
    )
    assert response.status_code == 401


def test_new_hashes_carry_the_prehash_marker(api):
    payload = {**REGISTER, "email": "marker@test.local"}
    api.post("/api/v1/accounts/register", payload, format="json")
    profile = StudentProfile.objects(email="marker@test.local").first()
    assert profile.password_hash.startswith("sha256$")
    assert len(profile.password_hash) == len("sha256$") + 60  # + bcrypt digest


def test_legacy_hash_still_verifies_and_upgrades(api):
    """Pre-hardening accounts (raw bcrypt) keep working, and their first
    successful login transparently re-hashes to the pre-hashed scheme."""
    import bcrypt as raw_bcrypt

    legacy_hash = raw_bcrypt.hashpw(b"password123", raw_bcrypt.gensalt()).decode()
    assert not legacy_hash.startswith("sha256$")
    StudentProfile(
        email="legacy@test.local",
        full_name="Legacy Student",
        password_hash=legacy_hash,
        created_at=datetime.now(timezone.utc),
    ).save()

    login = api.post(
        "/api/v1/accounts/login",
        {"email": "legacy@test.local", "password": "password123"},
        format="json",
    )
    assert login.status_code == 200

    profile = StudentProfile.objects(email="legacy@test.local").first()
    assert profile.password_hash.startswith("sha256$")  # upgraded in place
    assert profile.password_hash != legacy_hash

    # the upgraded hash verifies again on the next login
    assert api.post(
        "/api/v1/accounts/login",
        {"email": "legacy@test.local", "password": "password123"},
        format="json",
    ).status_code == 200


# ---------------------------------------------------------------------------
# Login throttling: fixed-window failure lockout per (email, IP)
# ---------------------------------------------------------------------------


def _login(api, email, password="wrong-password", **extra):
    return api.post(
        "/api/v1/accounts/login",
        {"email": email, "password": password},
        format="json",
        **extra,
    )


@override_settings(LOGIN_FAILURE_LIMIT=3)
def test_lockout_after_limit_failures(api):
    """`limit` failures lock the (email, IP) pair out — even the CORRECT
    password gets 429 while the window is open."""
    api.post("/api/v1/accounts/register", REGISTER, format="json")
    for _ in range(3):
        assert _login(api, REGISTER["email"]).status_code == 401
    response = _login(api, REGISTER["email"], REGISTER["password"])
    assert response.status_code == 429


@override_settings(LOGIN_FAILURE_LIMIT=3)
def test_successful_login_resets_failure_counter(api):
    """Two failures, a success, then two more failures must never trip the
    limit: a successful login clears the counter so legitimate users recover
    immediately."""
    api.post("/api/v1/accounts/register", REGISTER, format="json")
    assert _login(api, REGISTER["email"]).status_code == 401
    assert _login(api, REGISTER["email"]).status_code == 401
    assert _login(api, REGISTER["email"], REGISTER["password"]).status_code == 200
    assert _login(api, REGISTER["email"]).status_code == 401
    assert _login(api, REGISTER["email"]).status_code == 401
    # cumulative would be 4 failures without the reset; the limit is 3
    assert _login(api, REGISTER["email"], REGISTER["password"]).status_code == 200


@override_settings(LOGIN_FAILURE_LIMIT=3)
def test_lockout_is_scoped_per_email(api):
    """Locking one account must not lock another (no cross-account DoS)."""
    other = {**REGISTER, "email": "other@test.local"}
    api.post("/api/v1/accounts/register", REGISTER, format="json")
    api.post("/api/v1/accounts/register", other, format="json")
    for _ in range(3):
        assert _login(api, REGISTER["email"]).status_code == 401
    assert _login(api, REGISTER["email"], REGISTER["password"]).status_code == 429
    assert _login(api, other["email"], other["password"]).status_code == 200


@override_settings(LOGIN_FAILURE_LIMIT=3)
def test_lockout_is_scoped_per_ip(api):
    """The IP is part of the key: the same email from a different IP is free."""
    api.post("/api/v1/accounts/register", REGISTER, format="json")
    for _ in range(3):
        assert _login(api, REGISTER["email"], REMOTE_ADDR="10.9.9.9").status_code == 401
    assert (
        _login(api, REGISTER["email"], REGISTER["password"], REMOTE_ADDR="10.9.9.9").status_code
        == 429
    )
    assert (
        _login(api, REGISTER["email"], REGISTER["password"], REMOTE_ADDR="10.9.9.10").status_code
        == 200
    )


@override_settings(LOGIN_FAILURE_LIMIT=3, LOGIN_LOCKOUT_WINDOW_SECONDS=2)
def test_lockout_expires_after_window(api):
    """The lockout is a fixed window, not permanent: after it expires the
    account is reachable again."""
    api.post("/api/v1/accounts/register", REGISTER, format="json")
    for _ in range(3):
        assert _login(api, REGISTER["email"]).status_code == 401
    assert _login(api, REGISTER["email"], REGISTER["password"]).status_code == 429
    time.sleep(2.1)  # window is 2s; cache expiry is checked lazily
    assert _login(api, REGISTER["email"], REGISTER["password"]).status_code == 200




# ---------------------------------------------------------------------------
# Generic request caps: register / rl action / quiz attempt (security review)
# ---------------------------------------------------------------------------

from rest_framework.test import APIClient  # noqa: E402
from .auth import mint_tokens  # noqa: E402
from apps.rl_feedback.models import RLTransition  # noqa: E402


def _register_n(api, n):
    """Register `n` distinct accounts from the test client's fixed IP."""
    for i in range(n):
        response = api.post(
            "/api/v1/accounts/register",
            {**REGISTER, "email": f"cap{i}@test.local"},
            format="json",
        )
        assert response.status_code == 201


@override_settings(REGISTER_THROTTLE_LIMIT=3, REGISTER_THROTTLE_WINDOW_SECONDS=3600)
def test_register_throttled_after_limit(api):
    """After REGISTER_THROTTLE_LIMIT registrations from one IP inside the
    window, the next signup is a 429 — mass signup cannot run at full speed."""
    _register_n(api, 3)
    response = api.post(
        "/api/v1/accounts/register",
        {**REGISTER, "email": "over@cap.test.local"},
        format="json",
    )
    assert response.status_code == 429
    assert "Too many" in response.data["detail"]


@override_settings(REQUEST_THROTTLE_LIMIT=2, REQUEST_THROTTLE_WINDOW_SECONDS=60)
def test_rl_action_throttled(registered, monkeypatch):
    """After REQUEST_THROTTLE_LIMIT RL actions the next one is a 429 and the
    transition log stays untouched."""
    from careermind_ml.rl.dqn import DQNAgent

    monkeypatch.setattr("apps.rl_feedback.views._agent", DQNAgent({}))
    client, user = registered
    for _ in range(2):
        assert client.post("/api/v1/rl/action").status_code == 200
    response = client.post("/api/v1/rl/action")
    assert response.status_code == 429
    assert RLTransition.objects(student=user["student_id"]).count() == 2


@override_settings(REQUEST_THROTTLE_LIMIT=2, REQUEST_THROTTLE_WINDOW_SECONDS=60)
def test_quiz_attempt_throttled(registered):
    """Quiz attempts share the generic cap; over-limit posts are rejected
    before any write, so session counters cannot be inflated."""
    client, _ = registered
    from apps.courses.models import Quiz
    from apps.collector.models import BehaviourSession

    quiz = Quiz(
        skill="dsa",
        title="Throttle quiz",
        questions=[{"question": "Q?", "options": ["a", "b"], "answer": 0, "difficulty": 1}],
    ).save()
    session_id = client.post("/api/v1/collector/sessions/start").data["session_id"]

    for _ in range(2):
        response = client.post(
            f"/api/v1/courses/quizzes/{quiz.pk}/attempt",
            {"item_id": "q0", "selected": -1},
            format="json",
        )
        assert response.status_code == 201
    response = client.post(
        f"/api/v1/courses/quizzes/{quiz.pk}/attempt",
        {"item_id": "q0", "selected": -1},
        format="json",
    )
    assert response.status_code == 429
    session = BehaviourSession.objects(pk=session_id).first()
    assert session.quiz_items == 2  # the 429'd attempt wrote nothing


@override_settings(REQUEST_THROTTLE_LIMIT=2, REQUEST_THROTTLE_WINDOW_SECONDS=60)
def test_throttle_buckets_are_scoped_per_student(registered):
    """One student exhausting the request cap never throttles another."""
    client, _ = registered
    second = APIClient()
    reg = second.post(
        "/api/v1/accounts/register",
        {**REGISTER, "email": "second@test.local"},
        format="json",
    )
    assert reg.status_code == 201
    second.credentials(HTTP_AUTHORIZATION=f"Bearer {reg.data['access']}")
    for _ in range(2):
        assert client.post("/api/v1/rl/action").status_code == 200
    assert second.post("/api/v1/rl/action").status_code == 200
