"""Integration tests: item writes need a principal, item reads stay public.

The tests replace ``get_current_user``, so they hold in every auth variant. How
a variant turns credentials into a principal is tested in its ``test_auth.py``.
"""

import logging
from http import HTTPStatus

import pytest

from app.infrastructure.audit import AUDIT_LOGGER_NAME
from tests.audit_records import audit_records

pytestmark = pytest.mark.integration

UNKNOWN_ITEM_ID = "00000000-0000-4000-8000-000000000000"
VALID_BODY = {"name": "Widget", "price": 1.0}

WRITE_REQUESTS = [
    pytest.param("post", "", {"json": VALID_BODY}, id="create"),
    pytest.param("put", f"/{UNKNOWN_ITEM_ID}", {"json": {"name": "x"}}, id="update"),
    pytest.param("delete", f"/{UNKNOWN_ITEM_ID}", {}, id="delete"),
]


@pytest.fixture
def items_url(api_prefix: str) -> str:
    """Collection URL of the item routes."""
    return f"{api_prefix}/items"


@pytest.mark.parametrize(("method", "suffix", "options"), WRITE_REQUESTS)
def test_when_a_write_has_no_principal_then_401_with_the_authentication_envelope(
    unauthenticated_client, items_url, method, suffix, options
):
    """when no principal is resolved, each write answers 401 with a bearer challenge.

    Validates app.api.auth_deps.get_current_user().
    """
    response = getattr(unauthenticated_client, method)(items_url + suffix, **options)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_when_a_create_has_no_principal_then_nothing_is_stored(
    unauthenticated_client, items_url
):
    """when an unauthenticated create is rejected, the table stays empty.

    Validates app.api.v1.endpoints.items.create_item().
    """
    unauthenticated_client.post(items_url, json=VALID_BODY)

    assert unauthenticated_client.get(items_url).json()["total"] == 0


def test_when_the_caller_is_unknown_then_authentication_is_checked_before_the_body(
    unauthenticated_client, items_url
):
    """when an unauthenticated caller sends an invalid body, the answer is 401, not 422.

    Validation details must not be available to callers that did not authenticate.

    Validates app.api.v1.endpoints.items.create_item().
    """
    response = unauthenticated_client.post(items_url, json={"name": ""})

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert "details" not in response.json()["error"]


def test_when_a_write_has_no_principal_then_the_existence_of_an_item_is_not_revealed(
    unauthenticated_client, items_url
):
    """when an unauthenticated caller targets an unknown id, the answer is 401, not 404.

    Validates app.api.v1.endpoints.items.update_item().
    """
    response = unauthenticated_client.put(
        f"{items_url}/{UNKNOWN_ITEM_ID}", json={"name": "x"}
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_when_a_write_has_no_principal_then_nothing_is_audited(
    unauthenticated_client, items_url, caplog
):
    """when a write is rejected for missing credentials, no audit line is written.

    Validates app.api.v1.endpoints.items.create_item().
    """
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        unauthenticated_client.post(items_url, json=VALID_BODY)

    assert audit_records(caplog) == []


def test_when_reads_have_no_principal_then_they_stay_public(
    unauthenticated_client, items_url
):
    """when no principal is resolved, listing and fetching still work.

    Validates app.api.v1.endpoints.items.list_items().
    """
    listed = unauthenticated_client.get(items_url)
    missing = unauthenticated_client.get(f"{items_url}/{UNKNOWN_ITEM_ID}")

    assert listed.status_code == HTTPStatus.OK
    assert missing.status_code == HTTPStatus.NOT_FOUND


def test_when_a_principal_is_present_then_writes_succeed(
    authenticated_client, items_url
):
    """when a principal is resolved, create, update and delete all succeed.

    Validates app.api.v1.endpoints.items.create_item().
    """
    created = authenticated_client.post(items_url, json=VALID_BODY)
    item_url = f"{items_url}/{created.json()['id']}"

    assert created.status_code == HTTPStatus.CREATED
    assert (
        authenticated_client.put(item_url, json={"name": "Renamed"}).status_code
        == HTTPStatus.OK
    )
    assert authenticated_client.delete(item_url).status_code == HTTPStatus.NO_CONTENT
