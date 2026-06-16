"""Integration tests for GET /api/v1/users/me (issue #16).

Acceptance criteria:
- Returns 200 with `email` and `id` fields present.
- Strips secret fields (`password_hash`, `password`) via response_model=UserPublic.
- Resolves normally when no override is applied (base dev user).
"""

import pytest

from app.dependencies import get_current_user
from app.main import app

API = "/api/v1"


@pytest.mark.integration
def test_when_user_dict_has_secrets_then_response_strips_them(client):
    """when get_current_user returns a dict with password_hash and password,
    GET /api/v1/users/me returns 200 and the JSON omits both secret fields."""
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "email": "a@b.com",
        "username": "a",
        "is_active": True,
        "password_hash": "$2b$secret",
        "password": "plaintext",
    }
    try:
        response = client.get(f"{API}/users/me")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "u1"
        assert body["email"] == "a@b.com"
        assert "password_hash" not in body
        assert "password" not in body
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.integration
def test_when_real_dev_user_resolves_then_response_is_200_with_email(client):
    """when the real (un-overridden) base dev user resolves, GET /api/v1/users/me
    returns 200 with a valid email — proving the shipped dependency dict passes
    the UserPublic (EmailStr) response model, not just a test stub."""
    response = client.get(f"{API}/users/me")

    assert response.status_code == 200
    body = response.json()
    assert "@" in body["email"]
    assert "id" in body


@pytest.mark.integration
def test_when_user_id_header_given_then_response_is_200_with_email(client):
    """when an X-User-Id header drives get_current_user, the synthesized email
    is still a valid EmailStr and GET /api/v1/users/me returns 200."""
    response = client.get(f"{API}/users/me", headers={"X-User-Id": "abc123"})

    assert response.status_code == 200
    assert "@" in response.json()["email"]


@pytest.mark.integration
def test_when_openapi_fetched_then_users_me_has_summary_and_response_description(
    client,
):
    """when the OpenAPI schema is read, GET /users/me carries a summary and a
    documented success response description (#24)."""
    op = client.get("/openapi.json").json()["paths"]["/api/v1/users/me"]["get"]

    # Explicit summary, not the function-name-derived default ("Read Current User").
    assert op["summary"] == "Get the current user"
    assert op["responses"]["200"]["description"] != "Successful Response"
