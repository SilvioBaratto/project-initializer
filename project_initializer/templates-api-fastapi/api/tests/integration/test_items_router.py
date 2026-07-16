"""Integration tests for the DB-backed /api/v1/items router.

Scope: issue #9. Proves the router→service→repository→DB slice persists items
across separate requests (not per-request memory) and maps missing ids to 404.
Uses the `client` fixture (TestClient with `get_db` overridden by the rolled-back
`db_session`). Credential-free: auth lands in the next issue.
"""

import pytest

API = "/api/v1"


def _create(client, **overrides):
    """POST an item through the API and return the response JSON."""
    payload = {"name": "Widget", "description": "A widget", "price": 9.99}
    payload.update(overrides)
    resp = client.post(f"{API}/items", json=payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.integration
def test_when_item_posted_then_201_and_item_returned(client):
    """when an item is posted, 201 and the created item with an id are returned."""
    body = _create(client)

    assert body["id"]
    assert body["name"] == "Widget"
    assert body["price"] == 9.99


@pytest.mark.integration
def test_when_item_created_then_it_persists_across_requests(client):
    """when an item is created, a separate GET request reads it back from the DB."""
    created = _create(client, name="Persisted")

    fetched = client.get(f"{API}/items/{created['id']}")

    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]
    assert fetched.json()["name"] == "Persisted"


@pytest.mark.integration
def test_when_items_listed_then_created_item_is_in_the_list(client):
    """when items are listed, a previously created item appears with a total count."""
    created = _create(client, name="Listed")

    resp = client.get(f"{API}/items")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(it["id"] == created["id"] for it in body["items"])


@pytest.mark.integration
def test_when_item_updated_then_changes_are_returned(client):
    """when an item is updated, the updated fields are returned."""
    created = _create(client)

    resp = client.put(
        f"{API}/items/{created['id']}", json={"name": "Renamed", "price": 1.0}
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    assert resp.json()["price"] == 1.0


@pytest.mark.integration
def test_when_item_deleted_then_subsequent_get_returns_404(client):
    """when an item is deleted, a follow-up GET for it returns 404."""
    created = _create(client)

    assert client.delete(f"{API}/items/{created['id']}").status_code in (200, 204)
    assert client.get(f"{API}/items/{created['id']}").status_code == 404


@pytest.mark.integration
def test_when_missing_id_fetched_then_404(client):
    """when a missing id is fetched, 404 is returned."""
    assert client.get(f"{API}/items/does-not-exist").status_code == 404


@pytest.mark.integration
def test_when_missing_id_updated_then_404(client):
    """when a missing id is updated, 404 is returned."""
    resp = client.put(f"{API}/items/nope", json={"name": "x"})
    assert resp.status_code == 404


@pytest.mark.integration
def test_when_missing_id_deleted_then_404(client):
    """when a missing id is deleted, 404 is returned."""
    assert client.delete(f"{API}/items/nope").status_code == 404


@pytest.mark.integration
def test_when_test_items_route_hit_then_it_is_gone(client):
    """when the retired in-memory /test/items route is hit, it no longer exists (404)."""
    assert client.get(f"{API}/test/items").status_code == 404


# --- pagination + validated bounds (#22) ------------------------------------


@pytest.mark.integration
def test_when_limit_over_100_then_422_is_returned(client):
    """when limit exceeds 100, a 422 validation error is returned."""
    assert client.get(f"{API}/items?limit=101").status_code == 422


@pytest.mark.integration
def test_when_skip_negative_then_422_is_returned(client):
    """when skip is negative, a 422 validation error is returned."""
    assert client.get(f"{API}/items?skip=-1").status_code == 422


@pytest.mark.integration
def test_when_limit_applied_then_only_limit_items_are_returned(client):
    """when limit=2 is applied over 3 items, only 2 items are returned."""
    for n in range(3):
        _create(client, name=f"Paged{n}")
    body = client.get(f"{API}/items?limit=2").json()
    assert len(body["items"]) == 2


@pytest.mark.integration
def test_when_more_items_than_page_then_total_reflects_full_count(client):
    """when more items exist than the page limit, total reflects the full count."""
    for n in range(3):
        _create(client, name=f"Counted{n}")
    body = client.get(f"{API}/items?limit=2").json()
    assert body["total"] >= 3
    assert len(body["items"]) == 2


@pytest.mark.integration
def test_when_openapi_fetched_then_limit_advertises_min_1_max_100(client):
    """when the OpenAPI schema is read, the limit query param advertises 1..100."""
    params = client.get("/openapi.json").json()["paths"]["/api/v1/items"]["get"][
        "parameters"
    ]
    limit = next(p for p in params if p["name"] == "limit")
    assert limit["schema"]["maximum"] == 100
    assert limit["schema"]["minimum"] == 1


@pytest.mark.integration
def test_when_openapi_fetched_then_item_id_path_advertises_min_length(client):
    """when the OpenAPI schema is read, the item_id path param advertises minLength 1."""
    params = client.get("/openapi.json").json()["paths"]["/api/v1/items/{item_id}"][
        "get"
    ]["parameters"]
    item_id = next(p for p in params if p["name"] == "item_id")
    assert item_id["schema"].get("minLength") == 1


# --- path-operation docs: summary / response_description / 404 (#24) ---------


@pytest.mark.integration
def test_when_openapi_fetched_then_each_items_route_has_summary(client):
    """when the OpenAPI schema is read, every items path operation has an explicit summary.

    FastAPI auto-derives a summary from the function name (e.g. ``list_items`` ->
    "List Items"), so assert the explicit, curated summaries to prove they were set.
    """
    paths = client.get("/openapi.json").json()["paths"]
    collection = paths["/api/v1/items"]
    by_id = paths["/api/v1/items/{item_id}"]

    assert collection["get"]["summary"] == "List items"
    assert collection["post"]["summary"] == "Create an item"
    assert by_id["get"]["summary"] == "Get an item"
    assert by_id["put"]["summary"] == "Update an item"
    assert by_id["delete"]["summary"] == "Delete an item"


@pytest.mark.integration
def test_when_openapi_fetched_then_each_items_route_has_response_description(client):
    """when the OpenAPI schema is read, each items route documents its success response.

    FastAPI defaults response_description to "Successful Response"; assert each
    route overrides it so the test fails until a real description is supplied.
    """
    paths = client.get("/openapi.json").json()["paths"]
    collection = paths["/api/v1/items"]
    by_id = paths["/api/v1/items/{item_id}"]
    default = "Successful Response"

    assert collection["get"]["responses"]["200"]["description"] != default
    assert collection["post"]["responses"]["201"]["description"] != default
    assert by_id["get"]["responses"]["200"]["description"] != default
    assert by_id["put"]["responses"]["200"]["description"] != default
    assert by_id["delete"]["responses"]["204"]["description"] != default


@pytest.mark.integration
def test_when_openapi_fetched_then_item_id_routes_document_404(client):
    """when the OpenAPI schema is read, GET/PUT/DELETE /items/{item_id} declare a 404."""
    by_id = client.get("/openapi.json").json()["paths"]["/api/v1/items/{item_id}"]

    for method in ("get", "put", "delete"):
        assert by_id[method]["responses"]["404"]["description"] == "Item not found"


# --- BackgroundTasks audit-log demo on create (#26) --------------------------


@pytest.mark.integration
def test_when_item_created_then_audit_log_background_task_fires(client, monkeypatch):
    """when an item is created, the write_audit_log background task is invoked with
    the create action and the new item's id, and the 201 response is unchanged.

    Patch the name as bound in the handler module (the handler resolves
    ``app.api.v1.endpoints.items.write_audit_log``, not the source module).
    Starlette's TestClient runs background tasks before returning, so the
    assertion is reliable.
    """
    calls: list[tuple] = []
    monkeypatch.setattr(
        "app.api.v1.endpoints.items.write_audit_log",
        lambda action, resource_id: calls.append((action, resource_id)),
    )

    body = _create(client, name="Audited")

    assert body["id"]
    assert body["name"] == "Audited"
    assert calls == [("item.create", body["id"])]
