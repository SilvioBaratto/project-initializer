"""Integration tests of the route template the real application logs.

FastAPI 0.165 keeps the prefix handed to ``include_router`` out of
``scope["route"].path``, so a log line written from that attribute alone names
``/items/{item_id}`` instead of ``/api/v1/items/{item_id}``. The unit tests use
probe applications with direct routes and cannot see it; these requests go
through the routers exactly as ``create_application`` includes them. It also
does not set ``scope["route"]`` for plain Starlette routes, such as the
``/openapi.json`` route FastAPI registers itself.
"""

import logging
import uuid
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from app.api.docs import DOCS_PATHS
from app.api.errors import UNMATCHED_ROUTE
from app.api.middleware.logging import REQUEST_LOG_MESSAGE

pytestmark = pytest.mark.integration

LOGGING_LOGGER = "app.api.middleware.logging"
HANDLER_LOGGER = "app.api.handlers"
DOMAIN_ERROR_LOG_MESSAGE = "request.domain_error"
UNKNOWN_PATH = "/no-such-route"


@pytest.fixture
def item_template(api_prefix: str) -> str:
    """Template of the route that reads one item, as the docs promise it."""
    return f"{api_prefix}/items/{{item_id}}"


def test_when_a_nested_router_is_reached_then_the_request_log_keeps_the_prefix(
    authenticated_client: TestClient, api_prefix: str, item_template: str, caplog
):
    """when an item route answers, the access log names the full route template.

    The items router declares ``/items``, is nested in the version router and is
    included with the ``/api/v1`` prefix, so the template only exists whole once
    all three are joined.

    Validates app.api.errors.route_template().
    """
    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        response = authenticated_client.get(f"{api_prefix}/items/{uuid.uuid4()}")

    assert response.status_code == HTTPStatus.NOT_FOUND
    (record,) = [
        item for item in caplog.records if item.getMessage() == REQUEST_LOG_MESSAGE
    ]
    assert record.path == item_template


def test_when_a_nested_router_fails_then_the_error_log_keeps_the_prefix(
    authenticated_client: TestClient, api_prefix: str, item_template: str, caplog
):
    """when an item is missing, the handler logs the full route template.

    The handlers and the logging middleware both call ``route_template``, so
    both lines must carry the same template.

    Validates app.api.errors.route_template().
    """
    with caplog.at_level(logging.INFO, logger=HANDLER_LOGGER):
        authenticated_client.get(f"{api_prefix}/items/{uuid.uuid4()}")

    (record,) = [
        item for item in caplog.records if item.getMessage() == DOMAIN_ERROR_LOG_MESSAGE
    ]
    assert record.path == item_template


def test_when_no_route_matches_the_real_application_then_the_log_uses_the_fixed_label(
    client: TestClient, caplog
):
    """when an unknown path is requested, the access log holds the fixed label.

    The prefix lookup must not turn an unmatched request into a template.

    Validates app.api.errors.route_template().
    """
    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        response = client.get(UNKNOWN_PATH)

    assert response.status_code == HTTPStatus.NOT_FOUND
    (record,) = [
        item for item in caplog.records if item.getMessage() == REQUEST_LOG_MESSAGE
    ]
    assert record.path == UNMATCHED_ROUTE


@pytest.mark.parametrize("docs_path", sorted(DOCS_PATHS))
def test_when_a_docs_route_answers_then_the_request_log_names_that_route(
    client: TestClient, docs_path: str, caplog
):
    """when the docs are enabled, each docs route is logged under its own path.

    ``/openapi.json`` is a plain Starlette route that FastAPI registers itself;
    the two pages are routes of the application.

    Validates app.api.errors.route_template().
    """
    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        response = client.get(docs_path)

    assert response.status_code == HTTPStatus.OK
    (record,) = [
        item for item in caplog.records if item.getMessage() == REQUEST_LOG_MESSAGE
    ]
    assert record.path == docs_path
