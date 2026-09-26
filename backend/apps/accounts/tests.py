"""Auth tests (Phase 3): register -> login -> me round trip, JWT guards."""
import pytest

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
