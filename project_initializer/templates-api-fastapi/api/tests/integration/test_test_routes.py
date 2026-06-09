"""Integration tests for demo test routes and the DB-backed items CRUD slice.

Scope: issue #12. Covers `/api/v1/test/ping` + `/api/v1/test/echo` and the full
create→get→list→update→delete round-trip against `/api/v1/items`, proving items
persist across separate requests through the SQLite test DB.

Credential-free: the base variant's `get_current_user` resolves a dev user, so
writes need no header. Token/supabase 401 behavior is covered separately (#13).
The round-trip creates then deletes its own item, so it does not depend on (or
leave) shared row state — list membership is asserted, never an exact total.
"""

import pytest

API = "/api/v1"


@pytest.mark.integration
def test_when_ping_requested_then_pong_is_returned(client):
    """when GET /test/ping is requested, 200 and {'message': 'pong'} are returned."""
    resp = client.get(f"{API}/test/ping")

    assert resp.status_code == 200
    assert resp.json() == {"message": "pong"}


@pytest.mark.integration
def test_when_echo_get_called_then_path_message_is_echoed(client):
    """when GET /test/echo/{message} is called, the path message is echoed back."""
    resp = client.get(f"{API}/test/echo/hello")

    assert resp.status_code == 200
    assert resp.json()["echo"] == "hello"


@pytest.mark.integration
def test_when_echo_post_called_then_body_message_is_echoed(client):
    """when POST /test/echo is called, the body message is echoed back."""
    resp = client.post(f"{API}/test/echo", json={"message": "world"})

    assert resp.status_code == 200
    assert resp.json()["echo"] == "world"


@pytest.mark.integration
def test_when_item_crud_round_trips_then_it_persists_and_deletes(client):
    """when an item is created, it round-trips through the DB and a delete removes it."""
    # CREATE (201)
    created = client.post(
        f"{API}/items", json={"name": "Widget", "description": "A widget", "price": 9.99}
    )
    assert created.status_code == 201
    item_id = created.json()["id"]
    assert item_id

    # GET by id — read back from the DB in a separate request (persistence)
    fetched = client.get(f"{API}/items/{item_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Widget"

    # LIST — the created item is present
    listed = client.get(f"{API}/items")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1
    assert any(it["id"] == item_id for it in body["items"])

    # UPDATE — fields change
    updated = client.put(f"{API}/items/{item_id}", json={"name": "Renamed", "price": 1.0})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["price"] == 1.0

    # DELETE (204, no body) then follow-up GET → 404
    assert client.delete(f"{API}/items/{item_id}").status_code == 204
    assert client.get(f"{API}/items/{item_id}").status_code == 404
