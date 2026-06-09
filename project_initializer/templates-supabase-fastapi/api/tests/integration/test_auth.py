"""Supabase-variant auth tests (issue #13, overlay over the base template).

Asserts the offline 401 path: the async `get_current_user` raises 401 the moment
the Authorization header is absent, BEFORE any `_supabase.auth.get_user` call, so
these tests need no live Supabase backend and make no network request.

A bare ``TestClient(app)`` is used instead of the base ``client`` fixture on
purpose: the fixture's session-scoped ``test_engine`` calls
``Base.metadata.create_all`` on SQLite, and the supabase ``UserProfile.preferences``
column is Postgres ``JSONB`` (not SQLite-compilable). These auth routes 401 before
any DB access, so no engine/session is needed — and not constructing one with
``TestClient(app)`` (no context manager) also skips the lifespan ``init_db``,
keeping the test fully offline. Authenticated (valid-JWT) paths require a live
Supabase project and are intentionally out of scope here.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1"
client = TestClient(app)


@pytest.mark.integration
def test_when_me_called_without_token_then_401():
    """when /auth/me is called without an Authorization header, 401 is returned."""
    assert client.get(f"{API}/auth/me").status_code == 401


@pytest.mark.integration
def test_when_items_write_has_no_authorization_header_then_401():
    """when a protected items write has no Authorization header, 401 is returned."""
    resp = client.post(f"{API}/items", json={"name": "Widget", "price": 1.0})

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Path-operation docs (#25): summary / response_description / 401 on /auth/me
# ---------------------------------------------------------------------------


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
