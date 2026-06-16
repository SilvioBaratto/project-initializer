"""Token-variant auth tests (issue #13, overlay over the base template).

Covers `/auth/validate`, `/auth/me`, and the 401 on a protected items write
without credentials. The valid token is read from `settings.auth_token` so the
test passes regardless of the configured `AUTH_TOKEN`. Uses the base `client`
fixture (TestClient with `get_db` overridden) and plain `assert`.
"""

import pytest

from app.config import settings

API = "/api/v1"
TOKEN = settings.auth_token
AUTH_HEADER = {"Authorization": f"Bearer {TOKEN}"}


@pytest.mark.integration
def test_when_validate_gets_configured_token_then_authenticated_true(client):
    """when /auth/validate gets the configured token, authenticated is true."""
    resp = client.post(f"{API}/auth/validate", json={"token": TOKEN})

    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True


@pytest.mark.integration
def test_when_validate_gets_wrong_token_then_authenticated_false(client):
    """when /auth/validate gets a wrong token, authenticated is false."""
    resp = client.post(f"{API}/auth/validate", json={"token": "wrong-token-value"})

    assert resp.status_code == 200
    assert resp.json()["authenticated"] is False


@pytest.mark.integration
def test_when_validate_gets_invalid_token_then_200_not_401_is_the_locked_contract(
    client,
):
    """LOCKED CONTRACT: /auth/validate is a validity probe, not a guard.

    An invalid token is a successful *answer* to "is this token valid?", so the
    endpoint returns HTTP 200 with ``authenticated=False`` — NOT 401. 401 is
    reserved for guarded endpoints that refuse access (``/auth/me``, item
    writes). Do not flip this to 401 without changing this contract on purpose.
    """
    resp = client.post(
        f"{API}/auth/validate", json={"token": "definitely-not-the-token"}
    )

    assert resp.status_code == 200
    assert resp.status_code != 401
    assert resp.json()["authenticated"] is False


@pytest.mark.integration
def test_when_me_called_without_token_then_401(client):
    """when /auth/me is called without a Bearer token, 401 is returned."""
    assert client.get(f"{API}/auth/me").status_code == 401


@pytest.mark.integration
def test_when_me_called_with_valid_token_then_200(client):
    """when /auth/me is called with a valid Bearer token, 200 and the user are returned."""
    resp = client.get(f"{API}/auth/me", headers=AUTH_HEADER)

    assert resp.status_code == 200
    assert resp.json()["id"]


@pytest.mark.integration
def test_when_items_write_has_no_credentials_then_401(client):
    """when a protected items write has no credentials, 401 is returned."""
    resp = client.post(f"{API}/items", json={"name": "Widget", "price": 1.0})

    assert resp.status_code == 401
