"""Entra-variant auth tests (offline 401/403 paths + JWKS-mocked matrix).

Offline tests (no JWT fixture needed):
  - Missing Authorization header → 401 (no JWKS call, no DB access)
  - OpenAPI docs assertions

JWKS-mocked matrix (conftest patches _jwks_client — no network, no live tenant):
  - valid token → 200 + mapped claims (id, email)
  - bad signature → 401
  - wrong audience → 401
  - wrong tid → 401
  - missing scope → 403

A bare ``TestClient(app)`` is used: no context manager (skips lifespan
``init_db``), no DB engine (JSONB columns are SQLite-incompatible). Auth
routes short-circuit before any DB access so no engine is needed.
"""

import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1"
client = TestClient(app)


# ---------------------------------------------------------------------------
# Offline tests — preserved from before this issue
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_when_me_called_without_token_then_401():
    """when /auth/me is called without an Authorization header, 401 is returned."""
    assert client.get(f"{API}/auth/me").status_code == 401


@pytest.mark.integration
def test_when_items_write_has_no_authorization_header_then_401():
    """when a protected items write has no Authorization header, 401 is returned."""
    resp = client.post(f"{API}/items", json={"name": "Widget", "price": 1.0})

    assert resp.status_code == 401


@pytest.mark.integration
def test_when_openapi_fetched_then_me_carries_summary_and_response_description():
    """when the OpenAPI schema is read, GET /auth/me carries an explicit summary
    and overrides the default success response_description."""
    op = client.get("/openapi.json").json()["paths"]["/api/v1/auth/me"]["get"]

    assert op["summary"] == "Get the current user"
    assert op["responses"]["200"]["description"] != "Successful Response"


@pytest.mark.integration
def test_when_openapi_fetched_then_me_documents_401():
    """when the OpenAPI schema is read, GET /auth/me documents its 401 failure mode."""
    op = client.get("/openapi.json").json()["paths"]["/api/v1/auth/me"]["get"]

    assert op["responses"]["401"]["description"]


# ---------------------------------------------------------------------------
# JWKS-mocked matrix — fixtures from conftest.py
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_when_valid_token_then_200_with_id_and_email(make_token):
    """when a fully valid RS256 token is sent, /auth/me returns 200 with id and email."""
    token = make_token()
    resp = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert "email" in body


@pytest.mark.integration
def test_when_token_has_bad_signature_then_401(make_token):
    """when a token is signed by a different key than the JWKS mock returns, 401 is returned."""
    # Sign with a second key; the JWKS mock still returns the first public key
    other_private_key = generate_private_key(public_exponent=65537, key_size=2048)
    import jwt as _jwt

    import app.config as cfg
    import time

    now = int(time.time())
    token = _jwt.encode(
        {
            "iss": cfg.settings.entra_issuer,
            "aud": cfg.settings.entra_api_client_id,
            "tid": cfg.settings.entra_tenant_id,
            "oid": "some-oid",
            "preferred_username": "user@example.com",
            "scp": cfg.settings.entra_api_scope,
            "iat": now,
            "exp": now + 3600,
        },
        other_private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    resp = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401


@pytest.mark.integration
def test_when_token_has_wrong_aud_then_401(make_token):
    """when a token carries an aud not in _expected_audiences(), 401 is returned."""
    token = make_token(aud="wrong-audience-value")
    resp = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401


@pytest.mark.integration
def test_when_token_has_wrong_tid_then_401(make_token):
    """when a token's tid differs from settings.entra_tenant_id, 401 is returned."""
    token = make_token(tid="different-tenant-id")
    resp = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401


@pytest.mark.integration
def test_when_token_lacks_required_scp_then_403(make_token):
    """when a token's scp claim omits the required scope, 403 is returned."""
    token = make_token(scp="some_other_scope")
    resp = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403
