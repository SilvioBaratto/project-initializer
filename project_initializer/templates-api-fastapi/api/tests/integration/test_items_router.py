"""Integration tests for the item routes: router, service, repository and database."""

import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app.api.headers import RETRY_AFTER_HEADER
from app.domain.constants import (
    DEFAULT_PAGE_SIZE,
    ENTITY_ID_LENGTH,
    ITEM_DESCRIPTION_MAX_LENGTH,
    ITEM_NAME_MAX_LENGTH,
    ITEM_PRICE_MAX,
    MAX_OFFSET,
    MAX_PAGE_SIZE,
)
from app.infrastructure import database
from app.infrastructure.audit import AUDIT_LOGGER_NAME
from app.infrastructure.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.infrastructure.database import DatabaseManager
from app.infrastructure.settings import settings
from app.main import app
from tests.audit_records import audit_records
from tests.fakes import TEST_USER

pytestmark = pytest.mark.integration

MISSING_ITEM_ID = "00000000-0000-4000-8000-000000000000"
NUL_CHARACTER = "\x00"
UNREACHABLE_DATABASE_URL = "sqlite:////nonexistent-directory/app.db"
BREAKER_RESET_SECONDS = 60.0
SEEDED_ITEM_COUNT = 3
PAGE_SIZE = 2

INVALID_ITEM_BODIES = [
    pytest.param({}, "name", id="name-missing"),
    pytest.param({"name": ""}, "name", id="name-empty"),
    pytest.param({"name": 123}, "name", id="name-wrong-type"),
    pytest.param(
        {"name": "n" * (ITEM_NAME_MAX_LENGTH + 1)}, "name", id="name-over-limit"
    ),
    pytest.param(
        {"name": "Widget", "description": "d" * (ITEM_DESCRIPTION_MAX_LENGTH + 1)},
        "description",
        id="description-over-limit",
    ),
    pytest.param({"name": "Widget", "price": -1}, "price", id="price-negative"),
    pytest.param(
        {"name": "Widget", "price": ITEM_PRICE_MAX * 2}, "price", id="price-over-limit"
    ),
    pytest.param({"name": "Widget", "price": "free"}, "price", id="price-not-numeric"),
    pytest.param(
        {"name": "Widget", "is_active": "maybe"}, "is_active", id="flag-not-boolean"
    ),
]
NUL_BODIES = [
    pytest.param({"name": f"Wid{NUL_CHARACTER}get"}, "name", id="name"),
    pytest.param(
        {"name": "Widget", "description": f"{NUL_CHARACTER}"},
        "description",
        id="description",
    ),
]
NOT_AN_ITEM_ID = [
    pytest.param("x" * (ENTITY_ID_LENGTH + 1), id="too-long"),
    pytest.param("does-not-exist", id="not-a-uuid"),
    pytest.param("%00", id="nul-character"),
    pytest.param("12345", id="number"),
]
NON_FINITE_BODIES = [
    pytest.param('{"name": "Widget", "price": NaN}', id="nan"),
    pytest.param('{"name": "Widget", "price": Infinity}', id="infinity"),
    pytest.param('{"name": "Widget", "price": -Infinity}', id="negative-infinity"),
]
OUT_OF_RANGE_PAGINATION = [
    pytest.param({"limit": 0}, id="limit-zero"),
    pytest.param({"limit": -1}, id="limit-negative"),
    pytest.param({"limit": MAX_PAGE_SIZE + 1}, id="limit-over-maximum"),
    pytest.param({"limit": "many"}, id="limit-not-a-number"),
    pytest.param({"skip": -1}, id="skip-negative"),
    pytest.param({"skip": MAX_OFFSET + 1}, id="skip-over-maximum"),
    pytest.param({"skip": "some"}, id="skip-not-a-number"),
]
IN_RANGE_PAGINATION = [
    pytest.param({"limit": 1}, id="limit-minimum"),
    pytest.param({"limit": MAX_PAGE_SIZE}, id="limit-maximum"),
    pytest.param({"skip": 0}, id="skip-minimum"),
    pytest.param({"skip": MAX_OFFSET}, id="skip-maximum"),
]


@pytest.fixture
def items_url(api_prefix: str) -> str:
    """Collection URL of the item routes."""
    return f"{api_prefix}/items"


def error_of(response) -> dict[str, Any]:
    """The ``error`` object of an error-envelope response."""
    return response.json()["error"]


def test_when_item_is_posted_then_201_and_the_created_item_is_returned(
    authenticated_client, items_url, item_payload
):
    """when a valid item is posted, 201 and the stored item with a generated id return.

    Validates app.api.v1.endpoints.items.create_item().
    """
    response = authenticated_client.post(items_url, json=item_payload)

    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert str(uuid.UUID(body["id"])) == body["id"]
    assert {key: body[key] for key in item_payload} == item_payload
    assert body["is_active"] is True
    assert datetime.fromisoformat(body["created_at"]) <= datetime.fromisoformat(
        body["updated_at"]
    )


def test_when_only_a_name_is_posted_then_optional_fields_take_their_defaults(
    authenticated_client, items_url
):
    """when only the name is posted, description and price are null and the item active.

    Validates app.api.v1.endpoints.items.create_item().
    """
    body = authenticated_client.post(items_url, json={"name": "Minimal"}).json()

    assert (body["description"], body["price"], body["is_active"]) == (None, None, True)


def test_when_item_is_created_then_a_later_request_reads_it_back(
    authenticated_client, items_url, create_item
):
    """when an item is created, a separate GET returns the same stored item.

    Validates app.api.v1.endpoints.items.get_item().
    """
    created = create_item(name="Persisted")

    fetched = authenticated_client.get(f"{items_url}/{created['id']}")

    assert fetched.status_code == HTTPStatus.OK
    assert fetched.json() == created


def test_when_no_item_exists_then_the_list_is_empty(authenticated_client, items_url):
    """when the table is empty, the list has no items and a total of zero.

    Validates app.api.v1.endpoints.items.list_items().
    """
    response = authenticated_client.get(items_url)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"items": [], "total": 0}


def test_when_items_are_listed_then_total_counts_every_item(
    authenticated_client, items_url, create_item
):
    """when several items exist, the list returns all of them with the full total.

    Validates app.api.v1.endpoints.items.list_items().
    """
    created_ids = {
        create_item(name=f"Item {n}")["id"] for n in range(SEEDED_ITEM_COUNT)
    }

    body = authenticated_client.get(items_url).json()

    assert body["total"] == SEEDED_ITEM_COUNT
    assert {item["id"] for item in body["items"]} == created_ids


def test_when_limit_is_applied_then_only_that_many_items_come_back_with_the_full_total(
    authenticated_client, items_url, create_item
):
    """when limit is smaller than the item count, the page is cut and total is not.

    Validates app.api.pagination.PaginationParams.
    """
    for number in range(SEEDED_ITEM_COUNT):
        create_item(name=f"Item {number}")

    body = authenticated_client.get(items_url, params={"limit": PAGE_SIZE}).json()

    assert len(body["items"]) == PAGE_SIZE
    assert body["total"] == SEEDED_ITEM_COUNT


def test_when_skip_is_applied_then_consecutive_pages_do_not_overlap(
    authenticated_client, items_url, create_item
):
    """when two pages are read with skip, together they hold every item once.

    Validates app.api.pagination.PaginationParams.
    """
    created_ids = {
        create_item(name=f"Item {n}")["id"] for n in range(SEEDED_ITEM_COUNT)
    }

    first = authenticated_client.get(items_url, params={"limit": PAGE_SIZE}).json()
    second = authenticated_client.get(
        items_url, params={"skip": PAGE_SIZE, "limit": PAGE_SIZE}
    ).json()

    first_ids = [item["id"] for item in first["items"]]
    second_ids = [item["id"] for item in second["items"]]
    assert len(second_ids) == SEEDED_ITEM_COUNT - PAGE_SIZE
    assert set(first_ids).isdisjoint(second_ids)
    assert set(first_ids + second_ids) == created_ids


def test_when_skip_passes_the_last_item_then_the_page_is_empty_and_total_is_kept(
    authenticated_client, items_url, create_item
):
    """when skip is past the end, the page is empty while total still counts all.

    Validates app.api.pagination.PaginationParams.
    """
    create_item()

    body = authenticated_client.get(items_url, params={"skip": 5}).json()

    assert body == {"items": [], "total": 1}


@pytest.mark.parametrize("query", OUT_OF_RANGE_PAGINATION)
def test_when_pagination_is_out_of_range_then_422_names_the_parameter(
    authenticated_client, items_url, query
):
    """when skip or limit breaks its bound, 422 is returned and names the parameter.

    Validates app.api.pagination.PaginationParams.
    """
    response = authenticated_client.get(items_url, params=query)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    (parameter,) = query
    assert [detail["field"] for detail in error_of(response)["details"]] == [parameter]


@pytest.mark.parametrize("query", IN_RANGE_PAGINATION)
def test_when_pagination_is_on_a_boundary_then_the_request_succeeds(
    authenticated_client, items_url, query
):
    """when skip or limit sits on an allowed boundary, the list answers 200.

    Validates app.api.pagination.PaginationParams.
    """
    assert (
        authenticated_client.get(items_url, params=query).status_code == HTTPStatus.OK
    )


def test_when_the_schema_is_read_then_pagination_bounds_and_default_are_advertised(
    openapi_schema, items_url
):
    """when OpenAPI is generated, skip and limit publish their bounds and defaults.

    Validates app.api.pagination.PaginationParams.
    """
    parameters = openapi_schema["paths"][items_url]["get"]["parameters"]
    schemas = {parameter["name"]: parameter["schema"] for parameter in parameters}

    assert schemas["limit"]["minimum"] == 1
    assert schemas["limit"]["maximum"] == MAX_PAGE_SIZE
    assert schemas["limit"]["default"] == DEFAULT_PAGE_SIZE
    assert schemas["skip"]["minimum"] == 0
    assert schemas["skip"]["maximum"] == MAX_OFFSET
    assert schemas["skip"]["default"] == 0


def test_when_item_is_updated_then_the_changes_are_returned_and_stored(
    authenticated_client, items_url, create_item
):
    """when name and price are updated, the response and a later GET show them.

    Validates app.api.v1.endpoints.items.update_item().
    """
    created = create_item()

    response = authenticated_client.put(
        f"{items_url}/{created['id']}", json={"name": "Renamed", "price": 1.0}
    )

    assert response.status_code == HTTPStatus.OK
    assert (response.json()["name"], response.json()["price"]) == ("Renamed", 1.0)
    assert authenticated_client.get(f"{items_url}/{created['id']}").json() == (
        response.json()
    )


def test_when_update_sends_one_field_then_the_other_fields_are_untouched(
    authenticated_client, items_url, create_item
):
    """when only the name is sent, description, price and flag keep their values.

    Validates app.api.schemas.item.ItemUpdate.to_command().
    """
    created = create_item()

    updated = authenticated_client.put(
        f"{items_url}/{created['id']}", json={"name": "Renamed"}
    ).json()

    assert {**created, "name": "Renamed"} == {
        **updated,
        "updated_at": created["updated_at"],
    }


def test_when_update_sends_explicit_nulls_then_nullable_fields_are_cleared(
    authenticated_client, items_url, create_item
):
    """when description and price are sent as null, they are cleared.

    Validates app.api.schemas.item.ItemUpdate.to_command().
    """
    created = create_item()

    updated = authenticated_client.put(
        f"{items_url}/{created['id']}", json={"description": None, "price": None}
    ).json()

    assert (updated["description"], updated["price"]) == (None, None)
    assert updated["name"] == created["name"]


def test_when_update_deactivates_an_item_then_the_flag_is_stored(
    authenticated_client, items_url, create_item
):
    """when is_active is set to false, the item is stored as inactive.

    Validates app.api.v1.endpoints.items.update_item().
    """
    created = create_item()

    updated = authenticated_client.put(
        f"{items_url}/{created['id']}", json={"is_active": False}
    ).json()

    assert updated["is_active"] is False


def test_when_update_body_is_empty_then_the_item_is_returned_unchanged(
    authenticated_client, items_url, create_item
):
    """when the update body has no field, the item is returned as it was.

    Validates app.api.v1.endpoints.items.update_item().
    """
    created = create_item()

    response = authenticated_client.put(f"{items_url}/{created['id']}", json={})

    assert response.status_code == HTTPStatus.OK
    assert response.json() == created


@pytest.mark.parametrize("field", ["name", "is_active"])
def test_when_update_nulls_a_required_field_then_422_and_the_item_is_unchanged(
    authenticated_client, items_url, create_item, field
):
    """when a required field is sent as null, 422 names it and the item is unchanged.

    Validates app.api.schemas.item.ItemUpdate.
    """
    created = create_item()

    response = authenticated_client.put(
        f"{items_url}/{created['id']}", json={field: None}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert error_of(response)["code"] == "VALIDATION_ERROR"
    assert [detail["field"] for detail in error_of(response)["details"]] == [field]
    assert authenticated_client.get(f"{items_url}/{created['id']}").json() == created


def test_when_item_is_deleted_then_204_with_no_body_and_a_later_get_is_404(
    authenticated_client, items_url, create_item
):
    """when an item is deleted, 204 has no body and the item is gone afterwards.

    Validates app.api.v1.endpoints.items.delete_item().
    """
    created = create_item()

    deleted = authenticated_client.delete(f"{items_url}/{created['id']}")

    assert deleted.status_code == HTTPStatus.NO_CONTENT
    assert deleted.content == b""
    assert (
        authenticated_client.get(f"{items_url}/{created['id']}").status_code
        == HTTPStatus.NOT_FOUND
    )


@pytest.mark.parametrize(
    ("method", "options"),
    [
        pytest.param("get", {}, id="get"),
        pytest.param("put", {"json": {"name": "Renamed"}}, id="put"),
        pytest.param("delete", {}, id="delete"),
    ],
)
def test_when_item_is_missing_then_404_carries_the_not_found_envelope(
    authenticated_client, items_url, method, options
):
    """when the id is unknown, GET, PUT and DELETE answer 404 with NOT_FOUND.

    The body repeats the request id of the X-Request-ID response header.

    Validates app.api.handlers.handle_domain_error().
    """
    response = getattr(authenticated_client, method)(
        f"{items_url}/{MISSING_ITEM_ID}", **options
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    error = error_of(response)
    assert error["code"] == "NOT_FOUND"
    assert error["message"] == "Item not found"
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert MISSING_ITEM_ID not in response.text


@pytest.mark.parametrize("item_id", NOT_AN_ITEM_ID)
@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_when_item_id_is_not_a_uuid_then_422_names_the_path_parameter(
    authenticated_client, items_url, method, item_id
):
    """when the path id is not a UUID, validation rejects it before any lookup.

    Ids are generated UUIDs, so anything else, such as a NUL character that
    PostgreSQL cannot bind, never reaches the repository.

    Validates app.api.v1.endpoints.items.ItemId.
    """
    options = {"json": {"name": "x"}} if method == "put" else {}

    response = getattr(authenticated_client, method)(
        f"{items_url}/{item_id}", **options
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert [detail["field"] for detail in error_of(response)["details"]] == ["item_id"]


def test_when_item_id_is_uppercase_or_unhyphenated_then_it_finds_the_stored_item(
    authenticated_client, items_url, create_item
):
    """when the path writes a valid UUID in another notation, the same item is found.

    Validates app.api.v1.endpoints.items.get_item().
    """
    created = create_item()
    alternative_notation = uuid.UUID(created["id"]).hex.upper()

    response = authenticated_client.get(f"{items_url}/{alternative_notation}")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["id"] == created["id"]


@pytest.mark.parametrize(("body", "field"), INVALID_ITEM_BODIES)
def test_when_posted_body_is_invalid_then_422_names_the_field_and_nothing_is_stored(
    authenticated_client, items_url, body, field
):
    """when a body breaks a bound, 422 lists the field and no item is created.

    Validates app.api.schemas.item.ItemCreate.
    """
    response = authenticated_client.post(items_url, json=body)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert error_of(response)["code"] == "VALIDATION_ERROR"
    assert field in {detail["field"] for detail in error_of(response)["details"]}
    assert authenticated_client.get(items_url).json()["total"] == 0


@pytest.mark.parametrize(("body", "field"), NUL_BODIES)
def test_when_a_text_field_has_a_nul_character_then_422_and_nothing_is_stored(
    authenticated_client, items_url, body, field
):
    """when a text field holds a NUL character, creation is refused with a 422.

    PostgreSQL cannot bind it, so it would otherwise become a server error.

    Validates app.api.schemas.common.NulFreeStr.
    """
    response = authenticated_client.post(items_url, json=body)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert [detail["field"] for detail in error_of(response)["details"]] == [field]
    assert authenticated_client.get(items_url).json()["total"] == 0


@pytest.mark.parametrize(("body", "field"), NUL_BODIES)
def test_when_an_update_has_a_nul_character_then_422_and_the_item_is_unchanged(
    authenticated_client, items_url, create_item, body, field
):
    """when an update puts a NUL character in a text field, it is refused.

    Validates app.api.schemas.common.NulFreeStr.
    """
    created = create_item()

    response = authenticated_client.put(
        f"{items_url}/{created['id']}", json={field: body[field]}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert authenticated_client.get(f"{items_url}/{created['id']}").json() == created


def test_when_the_body_has_unknown_keys_then_they_are_ignored(
    authenticated_client, items_url, item_payload
):
    """when extra keys are posted, the item is created from the known fields only.

    Validates app.api.schemas.item.ItemCreate.
    """
    response = authenticated_client.post(
        items_url, json={**item_payload, "id": "chosen-by-client", "owner": "mallory"}
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["id"] != "chosen-by-client"
    assert "owner" not in response.json()


def test_when_rejected_value_is_long_then_the_error_does_not_repeat_it(
    authenticated_client, items_url
):
    """when an oversized name is rejected, the response does not echo it back.

    Validates app.api.handlers.handle_validation_error().
    """
    oversized_name = "n" * (ITEM_NAME_MAX_LENGTH + 1)

    response = authenticated_client.post(items_url, json={"name": oversized_name})

    assert oversized_name not in response.text


@pytest.mark.parametrize("raw_body", NON_FINITE_BODIES)
def test_when_price_is_not_finite_then_422_and_nothing_is_stored(
    authenticated_client, items_url, raw_body
):
    """when the price is NaN or infinite, the body is rejected.

    Validates app.api.schemas.item.ItemCreate.
    """
    response = authenticated_client.post(
        items_url, content=raw_body, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert authenticated_client.get(items_url).json()["total"] == 0


def test_when_name_is_only_whitespace_then_422_is_returned(
    authenticated_client, items_url
):
    """when the name is blank, the domain rule rejects it with 422.

    Validates app.application.commands.item.CreateItemCommand.to_new_item().
    """
    response = authenticated_client.post(items_url, json={"name": "   "})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert error_of(response)["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(("body", "field"), INVALID_ITEM_BODIES[1:])
def test_when_update_body_is_invalid_then_422_and_the_item_is_unchanged(
    authenticated_client, items_url, create_item, body, field
):
    """when an update breaks a bound, 422 lists the field and the item is intact.

    Validates app.api.schemas.item.ItemUpdate.
    """
    created = create_item()
    update = {key: value for key, value in body.items() if key == field}

    response = authenticated_client.put(f"{items_url}/{created['id']}", json=update)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert field in {detail["field"] for detail in error_of(response)["details"]}
    assert authenticated_client.get(f"{items_url}/{created['id']}").json() == created


def test_when_writes_succeed_then_each_one_is_audited_with_the_actor_id(
    authenticated_client, items_url, create_item, caplog
):
    """when an item is created, updated and deleted, each write is audited by actor id.

    The audit line names the actor by opaque id, never by email or username.

    Validates app.api.v1.endpoints.items.create_item().
    """
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        item_id = create_item()["id"]
        authenticated_client.put(f"{items_url}/{item_id}", json={"name": "Renamed"})
        authenticated_client.delete(f"{items_url}/{item_id}")

    assert [
        (record.action, record.resource_id, record.actor_id)
        for record in audit_records(caplog)
    ] == [
        (action, item_id, TEST_USER.id)
        for action in ("item.create", "item.update", "item.delete")
    ]
    assert TEST_USER.email not in caplog.text


def test_when_a_write_fails_then_nothing_is_audited(
    authenticated_client, items_url, caplog
):
    """when updating or deleting a missing item fails, no audit line is written.

    Validates app.api.v1.endpoints.items.update_item().
    """
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        authenticated_client.put(f"{items_url}/{MISSING_ITEM_ID}", json={"name": "x"})
        authenticated_client.delete(f"{items_url}/{MISSING_ITEM_ID}")
        authenticated_client.post(items_url, json={"name": ""})

    assert audit_records(caplog) == []


@pytest.fixture
def real_get_db_client(monkeypatch) -> Callable[[DatabaseManager], TestClient]:
    """Factory of a client that uses the real ``get_db`` over a given manager.

    The shared fixtures replace ``get_db``, so the path from a database failure
    to an HTTP response needs a client without that override.
    """

    def build(manager: DatabaseManager) -> TestClient:
        """Point ``get_db`` at ``manager`` and return a client for the real app."""
        monkeypatch.setattr(database, "database_manager", manager)
        return TestClient(app, raise_server_exceptions=False)

    return build


def unreachable_database_manager(breaker: CircuitBreaker | None = None):
    """A manager whose engine cannot open its database file."""
    return DatabaseManager(
        settings,
        breaker,
        engine_factory=lambda _settings: create_engine(UNREACHABLE_DATABASE_URL),
    )


def test_when_the_database_is_unreachable_then_503_with_retry_after_and_no_internals(
    real_get_db_client, items_url
):
    """when the database cannot be reached, a read answers 503 and hides the cause.

    The error is raised inside the ``get_db`` dependency's exception path; the
    handler must still translate it.

    Validates app.infrastructure.database.get_db().
    """
    client = real_get_db_client(unreachable_database_manager())

    response = client.get(items_url)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert error_of(response)["code"] == "SERVICE_UNAVAILABLE"
    assert RETRY_AFTER_HEADER in response.headers
    for leaked in ("sqlite", "nonexistent-directory", "unable to open"):
        assert leaked not in response.text.lower()


def test_when_the_circuit_is_open_then_the_answer_is_the_same_503(
    real_get_db_client, items_url
):
    """when failures opened the breaker, requests are refused with the same 503.

    Validates app.infrastructure.database.get_db().
    """
    breaker = CircuitBreaker(
        "database",
        CircuitBreakerConfig(
            failure_threshold=1, reset_timeout_seconds=BREAKER_RESET_SECONDS
        ),
        failure_types=(OperationalError,),
    )
    client = real_get_db_client(unreachable_database_manager(breaker))

    opening_response = client.get(items_url)
    refused_response = client.get(items_url)

    assert (
        refused_response.status_code
        == opening_response.status_code
        == HTTPStatus.SERVICE_UNAVAILABLE
    )
    assert error_of(refused_response)["code"] == error_of(opening_response)["code"]
    assert RETRY_AFTER_HEADER in refused_response.headers
