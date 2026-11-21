"""Unit tests of ``route_template`` on probe applications and hand-made scopes."""

import logging

import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from app.api.errors import UNMATCHED_ROUTE, route_template
from app.api.middleware.logging import REQUEST_LOG_MESSAGE, RequestLoggingMiddleware

pytestmark = pytest.mark.unit

LOGGING_LOGGER = "app.api.middleware.logging"
VERSION_PREFIX = "/api/v1"
LATE_PREFIX = "/late"
PLAIN_TEMPLATE = "/plain/{name}"
MOUNT_PATH = "/assets"


def paths_logged_for(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The ``path`` of every access-log record captured so far, oldest first."""
    return [
        item.path for item in caplog.records if item.getMessage() == REQUEST_LOG_MESSAGE
    ]


async def serve_plain(request: Request) -> PlainTextResponse:
    """Answer 200 from a plain Starlette route, which FastAPI does not wrap."""
    return PlainTextResponse("plain")


def plain_route_application(**route_options) -> FastAPI:
    """Application with the request-logging middleware and one plain route."""
    application = FastAPI()
    application.add_middleware(RequestLoggingMiddleware)
    application.add_route(PLAIN_TEMPLATE, serve_plain, **route_options)
    return application


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


def test_when_a_plain_route_answers_then_the_template_is_its_declared_path(caplog):
    """when a plain Starlette route serves the request, the log names its path.

    FastAPI 0.137 no longer puts such a route in ``scope["route"]``, which left
    the label at ``unmatched`` for them, ``/openapi.json`` included.

    Validates app.api.errors.route_template().
    """
    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        TestClient(plain_route_application()).get("/plain/any-name")

    assert paths_logged_for(caplog) == [PLAIN_TEMPLATE]


def test_when_a_plain_route_refuses_the_method_then_the_template_is_still_its_path(
    caplog,
):
    """when a plain route answers 405, the log still names its path.

    Validates app.api.errors.route_template().
    """
    application = plain_route_application(methods=["GET"])

    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        TestClient(application).post("/plain/any-name")

    assert paths_logged_for(caplog) == [PLAIN_TEMPLATE]


def test_when_a_mounted_application_answers_then_the_template_is_the_mount_path(
    caplog,
):
    """when a mounted application serves the request, the log names the mount path.

    The rest of the path is chosen by the caller and stays out of the log.

    Validates app.api.errors.route_template().
    """
    application = FastAPI()
    application.add_middleware(RequestLoggingMiddleware)
    application.mount(MOUNT_PATH, PlainTextResponse("asset"))

    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        TestClient(application).get(f"{MOUNT_PATH}/secret-file-name.png")

    assert paths_logged_for(caplog) == [MOUNT_PATH]


def test_when_the_scope_holds_the_endpoint_of_a_plain_route_then_its_path_is_returned():
    """when only the endpoint is in the scope, the plain route that owns it is named.

    Validates app.api.errors.route_template().
    """
    scope = {"app": plain_route_application(), "endpoint": serve_plain}

    assert route_template(scope) == PLAIN_TEMPLATE


def test_when_no_route_owns_the_endpoint_then_the_fixed_label_is_returned():
    """when no route of the application owns the endpoint, the fixed label is returned.

    Validates app.api.errors.route_template().
    """
    scope = {"app": FastAPI(), "endpoint": serve_plain}

    assert route_template(scope) == UNMATCHED_ROUTE
