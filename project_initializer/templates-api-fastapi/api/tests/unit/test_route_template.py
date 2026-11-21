"""Unit tests of ``route_template`` on probe applications and hand-made scopes."""

import logging

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.errors import UNMATCHED_ROUTE, route_template
from app.api.middleware.logging import REQUEST_LOG_MESSAGE, RequestLoggingMiddleware

pytestmark = pytest.mark.unit

LOGGING_LOGGER = "app.api.middleware.logging"
VERSION_PREFIX = "/api/v1"
LATE_PREFIX = "/late"


def paths_logged_for(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The ``path`` of every access-log record captured so far, oldest first."""
    return [
        item.path for item in caplog.records if item.getMessage() == REQUEST_LOG_MESSAGE
    ]


def probe_application() -> FastAPI:
    """Application whose item route is nested in two routers, then prefixed.

    The nesting mirrors ``create_application``: the inner router carries its own
    ``prefix``, the outer one is included with the version prefix.
    """
    application = FastAPI()
    application.add_middleware(RequestLoggingMiddleware)
    items = APIRouter(prefix="/items")

    @items.get("/{item_id}")
    def read_item(item_id: str) -> dict[str, str]:
        """Answer 200 for any item id."""
        return {"id": item_id}

    version_router = APIRouter()
    version_router.include_router(items)
    application.include_router(version_router, prefix=VERSION_PREFIX)
    return application


def test_when_routers_are_nested_and_prefixed_then_the_template_names_every_prefix(
    caplog,
):
    """when a route sits behind two routers and a prefix, the template is whole.

    Validates app.api.errors.route_template().
    """
    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        TestClient(probe_application()).get(f"{VERSION_PREFIX}/items/any-id")

    assert paths_logged_for(caplog) == [f"{VERSION_PREFIX}/items/{{item_id}}"]


def test_when_a_router_is_included_after_the_first_request_then_its_template_is_whole(
    caplog,
):
    """when routes are added late, their template is still resolved with the prefix.

    A lookup built once at the first request would miss them and fall back to the
    unprefixed path.

    Validates app.api.errors.route_template().
    """
    application = probe_application()
    client = TestClient(application)
    late = APIRouter(prefix="/things")

    @late.get("/{name}")
    def read_thing(name: str) -> dict[str, str]:
        """Answer 200 for any name."""
        return {"name": name}

    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        client.get(f"{VERSION_PREFIX}/items/first")
        application.include_router(late, prefix=LATE_PREFIX)
        client.get(f"{LATE_PREFIX}/things/second")

    assert paths_logged_for(caplog) == [
        f"{VERSION_PREFIX}/items/{{item_id}}",
        f"{LATE_PREFIX}/things/{{name}}",
    ]


def test_when_the_scope_has_no_application_then_the_route_own_path_is_returned():
    """when no application is in the scope, the route's declared path is used.

    Validates app.api.errors.route_template().
    """
    route = APIRoute("/standalone/{name}", endpoint=lambda name: name)

    assert route_template({"route": route}) == "/standalone/{name}"


def test_when_the_route_is_unknown_to_the_application_then_its_own_path_is_returned():
    """when the application does not list the route, its declared path is used.

    Validates app.api.errors.route_template().
    """
    route = APIRoute("/foreign/{name}", endpoint=lambda name: name)

    assert route_template({"app": FastAPI(), "route": route}) == "/foreign/{name}"


def test_when_the_scope_holds_no_route_then_the_fixed_label_is_returned():
    """when routing has not matched, the fixed label stands in for the path.

    Validates app.api.errors.route_template().
    """
    assert route_template({"app": FastAPI()}) == UNMATCHED_ROUTE
