"""Integration tests for the demo routes under ``/test``."""

from datetime import UTC, datetime
from http import HTTPStatus
from urllib.parse import quote

import pytest

from app.api.schemas.demo import (
    ECHO_MESSAGE_MAX_LENGTH,
    ECHO_METADATA_KEY_MAX_LENGTH,
    ECHO_METADATA_MAX_ITEMS,
    ECHO_METADATA_VALUE_MAX_LENGTH,
)

pytestmark = pytest.mark.integration

PATH_MESSAGES = [
    pytest.param("hello", id="ascii"),
    pytest.param("two words", id="space"),
    pytest.param("caffè ☕", id="unicode"),
    pytest.param("a" * ECHO_MESSAGE_MAX_LENGTH, id="at-the-limit"),
]
REJECTED_METADATA = [
    pytest.param(
        {f"key-{n}": "v" for n in range(ECHO_METADATA_MAX_ITEMS + 1)},
        id="too-many-items",
    ),
    pytest.param({"k" * (ECHO_METADATA_KEY_MAX_LENGTH + 1): "v"}, id="key-too-long"),
    pytest.param(
        {"key": "v" * (ECHO_METADATA_VALUE_MAX_LENGTH + 1)}, id="value-too-long"
    ),
    pytest.param({"key": 123}, id="value-not-text"),
]
ACCEPTED_METADATA = [
    pytest.param(
        {f"key-{n}": "v" for n in range(ECHO_METADATA_MAX_ITEMS)}, id="item-limit"
    ),
    pytest.param({"k" * ECHO_METADATA_KEY_MAX_LENGTH: "v"}, id="key-limit"),
    pytest.param({"key": "v" * ECHO_METADATA_VALUE_MAX_LENGTH}, id="value-limit"),
    pytest.param({}, id="empty"),
]


@pytest.fixture
def demo_url(api_prefix: str) -> str:
    """Base URL of the demo routes."""
    return f"{api_prefix}/test"


def test_when_ping_is_requested_then_pong_is_returned(client, demo_url):
    """when GET /test/ping is requested, 200 and the pong message are returned.

    Validates app.api.v1.endpoints.test.ping().
    """
    response = client.get(f"{demo_url}/ping")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"message": "pong"}


@pytest.mark.parametrize("message", PATH_MESSAGES)
def test_when_echo_get_is_called_then_the_path_message_is_echoed(
    client, demo_url, message
):
    """when GET /test/echo/{message} is called, the decoded message comes back.

    Validates app.api.v1.endpoints.test.echo_get().
    """
    response = client.get(f"{demo_url}/echo/{quote(message)}")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["echo"] == message
    assert body["metadata"] is None
    received_at = datetime.fromisoformat(body["received_at"])
    assert received_at.tzinfo is not None
    assert received_at <= datetime.now(UTC)


def test_when_echo_path_message_is_over_the_limit_then_422_names_the_parameter(
    client, demo_url
):
    """when the path message exceeds the limit, validation rejects it.

    Validates app.api.v1.endpoints.test.echo_get().
    """
    response = client.get(f"{demo_url}/echo/{'a' * (ECHO_MESSAGE_MAX_LENGTH + 1)}")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert [d["field"] for d in response.json()["error"]["details"]] == ["message"]


def test_when_echo_post_is_called_then_message_and_metadata_are_echoed(
    client, demo_url
):
    """when POST /test/echo is called, the body's message and labels come back.

    Validates app.api.v1.endpoints.test.echo_post().
    """
    response = client.post(
        f"{demo_url}/echo", json={"message": "world", "metadata": {"source": "docs"}}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["echo"] == "world"
    assert response.json()["metadata"] == {"source": "docs"}


@pytest.mark.parametrize("message", ["", "a" * ECHO_MESSAGE_MAX_LENGTH])
def test_when_echo_post_message_is_on_a_boundary_then_it_is_accepted(
    client, demo_url, message
):
    """when the body message is empty or at the limit, it is echoed.

    Validates app.api.schemas.demo.EchoRequest.
    """
    response = client.post(f"{demo_url}/echo", json={"message": message})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["echo"] == message


def test_when_echo_post_message_is_over_the_limit_then_422_names_the_field(
    client, demo_url
):
    """when the body message is one character too long, validation rejects it.

    Validates app.api.schemas.demo.EchoRequest.
    """
    response = client.post(
        f"{demo_url}/echo", json={"message": "a" * (ECHO_MESSAGE_MAX_LENGTH + 1)}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert [d["field"] for d in response.json()["error"]["details"]] == ["message"]


def test_when_echo_post_has_no_message_then_422_is_returned(client, demo_url):
    """when the body has no message, validation rejects it.

    Validates app.api.schemas.demo.EchoRequest.
    """
    response = client.post(f"{demo_url}/echo", json={})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize("metadata", ACCEPTED_METADATA)
def test_when_echo_metadata_is_on_a_boundary_then_it_is_echoed(
    client, demo_url, metadata
):
    """when metadata sits on a size boundary, it is accepted and echoed.

    Validates app.api.schemas.demo.EchoRequest.
    """
    response = client.post(
        f"{demo_url}/echo", json={"message": "m", "metadata": metadata}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["metadata"] == metadata


@pytest.mark.parametrize("metadata", REJECTED_METADATA)
def test_when_echo_metadata_breaks_a_bound_then_422_is_returned(
    client, demo_url, metadata
):
    """when metadata has too many items, a long key or value, or a non-text value, 422.

    Validates app.api.schemas.demo.EchoRequest.
    """
    response = client.post(
        f"{demo_url}/echo", json={"message": "m", "metadata": metadata}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert "metadata" in response.json()["error"]["details"][0]["field"]


def test_when_caller_has_no_principal_then_the_demo_routes_are_still_public(
    unauthenticated_client, demo_url
):
    """when no principal is resolved, ping and echo still answer 200.

    Validates app.api.v1.router.api_router.
    """
    ping = unauthenticated_client.get(f"{demo_url}/ping")
    echo = unauthenticated_client.post(f"{demo_url}/echo", json={"message": "m"})

    assert (ping.status_code, echo.status_code) == (200, 200)
