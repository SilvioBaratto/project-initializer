"""Auth-guard tests for the items write operations (issue #10).

The items router source is identical across all three variants; behavior comes
from each variant's ``dependencies.py``. These tests run in the BASE template:

- Base ``get_current_user`` never 401s, so credential-free writes succeed.
- To prove the guard is actually wired on writes (the token/supabase behavior),
  we override ``get_current_user`` to raise 401 and assert writes are blocked
  while reads stay open — exactly the write-only protection scope.
"""

import pytest
from fastapi import HTTPException, status

from app.dependencies import get_current_user
from app.main import app

API = "/api/v1"


def _raise_401():
    """Stand-in for the token/supabase get_current_user with no credentials."""
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@pytest.mark.integration
def test_when_base_variant_writes_without_credentials_then_they_succeed(client):
    """when the base variant writes without credentials, the dev user resolves and writes succeed."""
    created = client.post(f"{API}/items", json={"name": "Widget", "price": 1.0})
    assert created.status_code == 201

    item_id = created.json()["id"]
    assert client.put(f"{API}/items/{item_id}", json={"name": "Renamed"}).status_code == 200
    assert client.delete(f"{API}/items/{item_id}").status_code == 204


@pytest.mark.integration
def test_when_guarded_writes_have_no_credentials_then_401(client):
    """when get_current_user 401s, the write ops (POST/PUT/DELETE) return 401."""
    app.dependency_overrides[get_current_user] = _raise_401
    try:
        assert client.post(f"{API}/items", json={"name": "X", "price": 1.0}).status_code == 401
        assert client.put(f"{API}/items/some-id", json={"name": "X"}).status_code == 401
        assert client.delete(f"{API}/items/some-id").status_code == 401
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.integration
def test_when_get_current_user_401s_then_reads_remain_open(client):
    """when get_current_user 401s, the read ops (GET list and GET by id) are unaffected."""
    app.dependency_overrides[get_current_user] = _raise_401
    try:
        assert client.get(f"{API}/items").status_code == 200
        # missing id still 404 (route reached, not blocked by auth)
        assert client.get(f"{API}/items/nope").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
