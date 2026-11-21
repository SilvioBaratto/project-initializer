"""Integration tests of the base variant's authentication: the development principal.

Every authentication overlay replaces this file with tests of its own
credentials. The tests here use the real ``get_current_user``, so they also pin
the behaviour of the ``X-User-Id`` development header.
"""

import logging
from http import HTTPStatus

import pytest

from app.api.auth_deps import (
    DEV_USER_HEADER,
    DEV_USER_ID,
    DEV_USER_ID_MAX_LENGTH,
    DEVELOPMENT_AUTH_METHOD,
)
from app.infrastructure.audit import AUDIT_LOGGER_NAME
from app.infrastructure.database import get_db
from app.infrastructure.settings import settings
from app.main import app
from tests.audit_records import audit_records

pytestmark = pytest.mark.integration

VALID_HEADER_IDS = [
    pytest.param("a", id="single-character"),
    pytest.param("alice_1-B", id="all-allowed-character-kinds"),
    pytest.param("x" * DEV_USER_ID_MAX_LENGTH, id="maximum-length"),
]
INVALID_HEADER_IDS = [
    pytest.param("has space", id="space"),
    pytest.param("alice@example.com", id="email"),
    pytest.param("../etc/passwd", id="path"),
    pytest.param("semi;colon", id="punctuation"),
    pytest.param("x" * (DEV_USER_ID_MAX_LENGTH + 1), id="over-maximum-length"),
    pytest.param("", id="empty"),
]
LOCAL_ENVIRONMENTS = ["development", "test"]
DEPLOYED_ENVIRONMENTS = ["staging", "production"]


@pytest.fixture
def me_url(api_prefix: str) -> str:
    """URL of the current-user route."""
    return f"{api_prefix}/auth/me"


def test_when_no_header_is_sent_then_the_caller_is_the_development_principal(
    client, me_url
):
    """when no credentials are sent, /auth/me returns the constant development user.

    Validates app.api.auth_deps.get_current_user().
    """
    response = client.get(me_url)

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["id"] == DEV_USER_ID
    assert body["auth_method"] == DEVELOPMENT_AUTH_METHOD
    assert body["roles"] == []


@pytest.mark.parametrize("user_id", VALID_HEADER_IDS)
def test_when_a_valid_user_id_header_is_sent_in_a_local_environment_then_it_is_used(
    client, me_url, user_id
):
    """when X-User-Id matches the pattern in a test run, the principal takes that id.

    Validates app.api.auth_deps.get_current_user().
    """
    response = client.get(me_url, headers={DEV_USER_HEADER: user_id})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["id"] == user_id


@pytest.mark.parametrize("user_id", INVALID_HEADER_IDS)
def test_when_the_user_id_header_breaks_the_pattern_then_422_without_the_value(
    client, me_url, user_id
):
    """when X-User-Id has a bad character, a bad length or is empty, 422 is returned.

    Validates app.api.auth_deps.get_current_user().
    """
    response = client.get(me_url, headers={DEV_USER_HEADER: user_id})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert [d["field"] for d in response.json()["error"]["details"]] == [
        DEV_USER_HEADER
    ]
    if user_id:
        assert user_id not in response.text


@pytest.mark.parametrize("environment", LOCAL_ENVIRONMENTS)
def test_when_environment_is_local_then_the_user_id_header_is_honoured(
    client, me_url, monkeypatch, environment
):
    """when the environment is development or test, X-User-Id selects the principal.

    Validates app.api.auth_deps.get_current_user().
    """
    monkeypatch.setattr(settings, "environment", environment)

    response = client.get(me_url, headers={DEV_USER_HEADER: "alice"})

    assert response.json()["id"] == "alice"


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_when_environment_is_deployed_then_the_user_id_header_is_ignored(
    client, me_url, monkeypatch, environment
):
    """when the environment is staging or production, X-User-Id cannot pick a user.

    Validates app.api.auth_deps.get_current_user().
    """
    monkeypatch.setattr(settings, "environment", environment)

    response = client.get(me_url, headers={DEV_USER_HEADER: "alice"})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["id"] == DEV_USER_ID


def test_when_the_principal_is_resolved_then_no_database_is_touched(client, me_url):
    """when /auth/me is requested, the database dependency is never used.

    Validates app.api.auth_deps.get_current_user().
    """

    def fail_if_used():
        """Fail the test when a request opens a database session."""
        raise AssertionError("resolving the development principal opened a session")

    app.dependency_overrides[get_db] = fail_if_used

    assert client.get(me_url).status_code == HTTPStatus.OK


def test_when_the_schema_is_read_then_the_dev_header_is_documented_with_its_pattern(
    openapi_schema, me_url
):
    """when OpenAPI is generated, /auth/me lists X-User-Id with its pattern and limit.

    Validates app.api.auth_deps.get_current_user().
    """
    parameters = openapi_schema["paths"][me_url]["get"]["parameters"]
    header = next(p for p in parameters if p["name"].lower() == DEV_USER_HEADER.lower())

    assert header["in"] == "header"
    assert header["required"] is False
    assert header["schema"]["anyOf"][0]["maxLength"] == DEV_USER_ID_MAX_LENGTH


def test_when_no_credentials_are_sent_then_writes_succeed_as_the_development_user(
    client, api_prefix, item_payload, caplog
):
    """when nothing identifies the caller, a create succeeds and is audited as dev-user.

    Validates app.api.auth_deps.get_current_user().
    """
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        response = client.post(f"{api_prefix}/items", json=item_payload)

    assert response.status_code == HTTPStatus.CREATED
    assert [record.actor_id for record in audit_records(caplog)] == [DEV_USER_ID]


def test_when_the_user_id_header_is_sent_then_writes_are_audited_under_that_id(
    client, api_prefix, item_payload, caplog
):
    """when X-User-Id names a user, the audit line carries that id as actor.

    Validates app.api.auth_deps.get_current_user().
    """
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        client.post(
            f"{api_prefix}/items",
            json=item_payload,
            headers={DEV_USER_HEADER: "alice"},
        )

    assert [record.actor_id for record in audit_records(caplog)] == ["alice"]
