"""Backend test fixtures: wipe the isolated careermind_test DB per test."""
import pytest
from django.conf import settings as django_settings
from pymongo import MongoClient


@pytest.fixture(autouse=True)
def clean_test_db():
    client = MongoClient(django_settings.MONGO_URI)
    client.drop_database(django_settings.MONGO_DB_NAME)
    yield
    client.drop_database(django_settings.MONGO_DB_NAME)


@pytest.fixture
def api():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def registered():
    """Register a student; returns (client-with-bearer, user_payload)."""
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.post(
        "/api/v1/accounts/register",
        {
            "email": "student@test.local",
            "full_name": "Test Student",
            "password": "password123",
            "programme": "BE Computer Science",
        },
        format="json",
    )
    assert response.status_code == 201
    token = response.data["access"]
    auth_client = APIClient()
    auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return auth_client, response.data
