"""JWT auth integration tests (issue #18) — OAuth2-password + JWT flow.

Covers the opt-in JWT endpoints added to the token-fastapi variant:
  - POST /auth/register   → 201 + UserPublic (no credentials in body)
  - POST /auth/token      → access_token + token_type bearer
  - GET  /auth/me/jwt     → 200 + user email when JWT supplied
  - GET  /auth/me/jwt     → 401 when no token
  - POST /auth/token      → 401 on wrong password
  - POST /auth/register   → 400 on duplicate email
  - POST /auth/validate   → static mode still works (regression guard)

Naming convention: "when X, Y is returned".
Marker: @pytest.mark.integration
Uses the `client` fixture from conftest (SQLite StaticPool, per-test rollback).
Distinct emails per test prevent cross-test collisions in the shared session.
"""

import pytest

from app.config import settings

API = "/api/v1"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_when_new_user_registers_201_is_returned_with_user_public_body(client):
    """when a new user registers, 201 is returned and the body has email + id
    but no password or password_hash."""
    resp = client.post(
        f"{API}/auth/register",
        json={"email": "jwt-register@example.com", "password": "strongpassword", "username": "jwtregister"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "jwt-register@example.com"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.integration
def test_when_duplicate_email_registered_400_is_returned(client):
    """when registering a duplicate email, 400 is returned."""
    payload = {"email": "jwt-dup@example.com", "password": "strongpassword"}
    client.post(f"{API}/auth/register", json=payload)

    resp = client.post(f"{API}/auth/register", json=payload)

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Token issuance
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_when_registered_user_logs_in_access_token_and_bearer_type_returned(client):
    """when registering then logging in via form, access_token + token_type
    bearer is returned."""
    client.post(
        f"{API}/auth/register",
        json={"email": "jwt-login@example.com", "password": "strongpassword"},
    )

    resp = client.post(
        f"{API}/auth/token",
        data={"username": "jwt-login@example.com", "password": "strongpassword"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.integration
def test_when_token_receives_wrong_password_401_is_returned(client):
    """when /token gets a wrong password, 401 is returned."""
    client.post(
        f"{API}/auth/register",
        json={"email": "jwt-badpw@example.com", "password": "correctpassword"},
    )

    resp = client.post(
        f"{API}/auth/token",
        data={"username": "jwt-badpw@example.com", "password": "wrongpassword"},
    )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# JWT-protected route
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_when_jwt_protected_route_called_with_valid_token_200_and_email_returned(client):
    """when the JWT-protected route is called with the minted bearer token,
    200 and the user email is returned."""
    client.post(
        f"{API}/auth/register",
        json={"email": "jwt-me@example.com", "password": "strongpassword"},
    )
    token_resp = client.post(
        f"{API}/auth/token",
        data={"username": "jwt-me@example.com", "password": "strongpassword"},
    )
    token = token_resp.json()["access_token"]

    resp = client.get(
        f"{API}/auth/me/jwt",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert resp.json()["email"] == "jwt-me@example.com"


@pytest.mark.integration
def test_when_jwt_protected_route_called_without_token_401_is_returned(client):
    """when the JWT-protected route is called WITHOUT a token, 401 is returned."""
    resp = client.get(f"{API}/auth/me/jwt")

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Static-mode regression guard
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_when_validate_receives_configured_auth_token_authenticated_is_true(client):
    """(static-mode still works) when /auth/validate gets the configured AUTH_TOKEN,
    authenticated is true."""
    resp = client.post(
        f"{API}/auth/validate",
        json={"token": settings.auth_token},
    )

    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True


# ---------------------------------------------------------------------------
# Path-operation docs (#25): summary / response_description / error responses
# ---------------------------------------------------------------------------

_DEFAULT_RESPONSE_DESCRIPTION = "Successful Response"


@pytest.mark.integration
def test_when_openapi_fetched_then_jwt_routes_carry_explicit_summaries(client):
    """when the OpenAPI schema is read, the JWT auth routes carry explicit summaries."""
    paths = client.get("/openapi.json").json()["paths"]

    assert paths["/api/v1/auth/register"]["post"]["summary"] == "Register a new user"
    assert paths["/api/v1/auth/token"]["post"]["summary"] == "Log in for an access token"
    assert paths["/api/v1/auth/me/jwt"]["get"]["summary"] == "Get the current JWT user"


@pytest.mark.integration
def test_when_openapi_fetched_then_jwt_routes_describe_success_response(client):
    """when the OpenAPI schema is read, each JWT route overrides the default
    success response_description."""
    paths = client.get("/openapi.json").json()["paths"]
    register = paths["/api/v1/auth/register"]["post"]["responses"]
    token = paths["/api/v1/auth/token"]["post"]["responses"]
    me = paths["/api/v1/auth/me/jwt"]["get"]["responses"]

    assert register["201"]["description"] != _DEFAULT_RESPONSE_DESCRIPTION
    assert token["200"]["description"] != _DEFAULT_RESPONSE_DESCRIPTION
    assert me["200"]["description"] != _DEFAULT_RESPONSE_DESCRIPTION


@pytest.mark.integration
def test_when_openapi_fetched_then_jwt_routes_document_error_responses(client):
    """when the OpenAPI schema is read, the JWT routes document their 400/401
    failure modes."""
    paths = client.get("/openapi.json").json()["paths"]

    assert paths["/api/v1/auth/register"]["post"]["responses"]["400"]["description"]
    assert paths["/api/v1/auth/token"]["post"]["responses"]["401"]["description"]
    assert paths["/api/v1/auth/me/jwt"]["get"]["responses"]["401"]["description"]
