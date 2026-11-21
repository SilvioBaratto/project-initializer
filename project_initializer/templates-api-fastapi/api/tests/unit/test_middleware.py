"""Unit tests for the request-logging, rate-limiting, security-header and
catch-all middleware.

Each class is exercised on a small probe application. Their composition on the
real application lives in ``tests/integration/test_app_middleware.py``.
"""

import asyncio
import logging
import re
from http import HTTPStatus
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.docs import (
    DOCS_CONTENT_SECURITY_POLICY,
    DOCS_PAGE_PATHS,
    DOCS_PATHS,
    OPENAPI_PATH,
)
from app.api.errors import UNMATCHED_ROUTE
from app.api.handlers import GENERIC_SERVER_ERROR_MESSAGE, INTERNAL_ERROR_CODE
from app.api.headers import (
    LIMIT_HEADER,
    REMAINING_HEADER,
    REQUEST_ID_HEADER,
    RESET_HEADER,
    RETRY_AFTER_HEADER,
)
from app.api.middleware.logging import REQUEST_LOG_MESSAGE, RequestLoggingMiddleware
from app.api.middleware.rate_limiting import RATE_LIMITED_CODE, RateLimitingMiddleware
from app.api.middleware.security import (
    API_CONTENT_SECURITY_POLICY,
    BASE_SECURITY_HEADERS,
    CONTENT_SECURITY_POLICY_HEADER,
    SecurityHeadersMiddleware,
)
from app.api.middleware.unhandled_errors import UnhandledErrorMiddleware
from app.infrastructure.request_context import current_request_id

pytestmark = pytest.mark.unit

LOGGING_LOGGER = "app.api.middleware.logging"
HANDLER_LOGGER = "app.api.handlers"
UNEXPECTED_ERROR_LOG_MESSAGE = "request.unhandled_exception"
GENERATED_ID = re.compile(r"^[0-9a-f]{32}$")
RATE_LIMIT = 3
IDLE_CLIENT_COUNT = 5
WINDOW_SECONDS = 60
TRACKED_CLIENT_CAP = 2
QUERY_VALUE = "query-value-that-must-not-be-logged"
BODY_VALUE = "body-value-that-must-not-be-logged"
CLIENT_ADDRESS = "203.0.113.77"
SPOOFED_FORWARDED_FOR = "198.51.100.9"
ROUTE_TEMPLATE = "/items/{item_id}"
SECRET_PATH_TEXT = "text-that-must-not-be-logged"
CRASH_DETAIL = "route failure"
EXEMPT_PATHS = ["/", "/health", "/health/ready"]
VALID_INCOMING_IDS = [
    pytest.param("client-id.1_2-3", id="mixed-characters"),
    pytest.param("a", id="single-character"),
    pytest.param("x" * 64, id="maximum-length"),
]
INVALID_INCOMING_IDS = [
    pytest.param("has space", id="space"),
    pytest.param("x" * 65, id="over-maximum-length"),
    pytest.param("a/b", id="slash"),
    pytest.param("new\\nline", id="backslash"),
    pytest.param("", id="empty"),
]


class FakeClock:
    """Monotonic clock that the test advances by hand."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward."""
        self.now += seconds


def add_plain_routes(application: FastAPI) -> None:
    """Add routes that answer without looking at the request."""

    @application.get("/echo")
    def echo() -> dict[str, bool]:
        """Answer 200."""
        return {"ok": True}

    @application.post("/submit")
    def submit(payload: dict[str, Any]) -> dict[str, bool]:
        """Accept any JSON object."""
        return {"ok": True}

    @application.get("/crash")
    def crash() -> None:
        """Fail with an unhandled exception."""
        raise RuntimeError(CRASH_DETAIL)

    @application.get(ROUTE_TEMPLATE)
    def read_item(item_id: str) -> dict[str, str]:
        """Answer 200 for any item id."""
        return {"item_id": item_id}

    for path in (*EXEMPT_PATHS, *DOCS_PATHS, "/api/docs"):
        application.add_api_route(path, echo, methods=["GET"])


def add_identity_routes(application: FastAPI) -> None:
    """Add routes that report the request id the middleware assigned."""

    @application.get("/identity")
    def identity(request: Request) -> dict[str, str | None]:
        """Report the request id as the handler and the log context see it."""
        return {"state": request.state.request_id, "context": current_request_id()}

    @application.get("/identity-async")
    async def identity_async(request: Request) -> dict[str, str | None]:
        """Report the request id from a coroutine route."""
        return {"state": request.state.request_id, "context": current_request_id()}


def probe_app() -> FastAPI:
    """A bare application with the routes the middleware tests need."""
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    add_plain_routes(application)
    add_identity_routes(application)
    return application


def logging_client(**client_options: Any) -> TestClient:
    """Client for the probe app behind the request-logging middleware."""
    application = probe_app()
    application.add_middleware(RequestLoggingMiddleware)
    return TestClient(application, raise_server_exceptions=False, **client_options)


def limited_client(
    clock: FakeClock,
    *,
    client_address: str = "10.0.0.1",
    **limiter_options: Any,
) -> TestClient:
    """Client for the probe app behind a limiter of ``RATE_LIMIT`` per window."""
    application = probe_app()
    # Starlette makes the last added middleware the outermost; the limiter must
    # sit inside the logging layer, as in the real application, to see the id.
    application.add_middleware(
        RateLimitingMiddleware,
        requests=RATE_LIMIT,
        window_seconds=WINDOW_SECONDS,
        clock=clock,
        **limiter_options,
    )
    application.add_middleware(RequestLoggingMiddleware)
    return TestClient(application, client=(client_address, 5000))


def guarded_client() -> TestClient:
    """Client for the probe app behind the real layers around the catch-all.

    The client re-raises server exceptions, so a test fails when the catch-all
    lets one through.
    """
    application = probe_app()
    application.add_middleware(UnhandledErrorMiddleware)
    application.add_middleware(SecurityHeadersMiddleware, docs_enabled=False)
    application.add_middleware(RequestLoggingMiddleware)
    return TestClient(application)


def same_limiter_other_address(client: TestClient, address: str) -> TestClient:
    """A client for the same application, connecting from another address."""
    return TestClient(client.app, client=(address, 5000))


def secured_client(*, docs_enabled: bool) -> TestClient:
    """Client for the probe app behind the security-header middleware."""
    application = probe_app()
    application.add_middleware(SecurityHeadersMiddleware, docs_enabled=docs_enabled)
    return TestClient(application)


def exhaust_quota(client: TestClient) -> None:
    """Send exactly the requests the limiter allows in one window."""
    for _ in range(RATE_LIMIT):
        assert client.get("/echo").status_code == HTTPStatus.OK


async def run_asgi(application, scope_type: str = "http") -> list[dict[str, Any]]:
    """Call an ASGI application once and return every message it sent."""
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        """Deliver an empty request body."""
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        """Collect an outgoing ASGI message."""
        sent.append(message)

    scope = {"type": scope_type, "method": "GET", "path": "/x", "headers": []}
    await application(scope, receive, send)
    return sent


def records_of(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Records the request-logging middleware emitted."""
    return [record for record in caplog.records if record.name == LOGGING_LOGGER]


def test_when_request_has_no_id_then_a_fresh_one_is_generated_and_returned():
    """when no X-Request-ID arrives, a 32-hex id is created and sent back.

    Validates app.api.middleware.logging.RequestLoggingMiddleware.
    """
    client = logging_client()

    first = client.get("/echo").headers[REQUEST_ID_HEADER]
    second = client.get("/echo").headers[REQUEST_ID_HEADER]

    assert GENERATED_ID.fullmatch(first)
    assert first != second


@pytest.mark.parametrize("incoming", VALID_INCOMING_IDS)
def test_when_request_carries_a_valid_id_then_it_is_reused(incoming):
    """when a well-formed X-Request-ID arrives, the response repeats it.

    Validates app.api.middleware.logging.RequestLoggingMiddleware.
    """
    response = logging_client().get("/echo", headers={REQUEST_ID_HEADER: incoming})

    assert response.headers[REQUEST_ID_HEADER] == incoming


@pytest.mark.parametrize("incoming", INVALID_INCOMING_IDS)
def test_when_request_carries_a_malformed_id_then_it_is_replaced(incoming):
    """when X-Request-ID is too long, empty or has odd characters, a new id is issued.

    Hostile header values must not reach the log pipeline.

    Validates app.api.middleware.logging.RequestLoggingMiddleware.
    """
    response = logging_client().get("/echo", headers={REQUEST_ID_HEADER: incoming})

    assert GENERATED_ID.fullmatch(response.headers[REQUEST_ID_HEADER])


@pytest.mark.parametrize("route", ["/identity", "/identity-async"])
def test_when_a_route_runs_then_state_and_log_context_both_hold_the_response_id(route):
    """when a sync or async route runs, request.state and the contextvar carry the id.

    Validates app.api.middleware.logging.RequestLoggingMiddleware.
    """
    response = logging_client().get(route)

    request_id = response.headers[REQUEST_ID_HEADER]
    assert response.json() == {"state": request_id, "context": request_id}


async def test_when_a_request_finishes_then_the_request_id_binding_is_released():
    """when the application returns, the contextvar is back to None.

    Validates app.api.middleware.logging.RequestLoggingMiddleware.
    """
    seen_inside: list[str | None] = []

    async def inner_app(scope, receive, send) -> None:
        """Record the bound id, then answer 204."""
        seen_inside.append(current_request_id())
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive() -> dict[str, Any]:
        """Deliver an empty request body."""
        return {"type": "http.request", "body": b"", "more_body": False}

    async def discard(_message) -> None:
        """Drop every outgoing ASGI message."""

    scope = {"type": "http", "method": "GET", "path": "/x", "headers": []}

    await RequestLoggingMiddleware(inner_app)(scope, receive, discard)

    assert seen_inside == [scope["state"]["request_id"]]
    assert current_request_id() is None


def test_when_a_request_completes_then_one_access_line_is_logged(caplog):
    """when a request finishes, exactly one http.request record has the access fields.

    Validates app.api.middleware.logging.RequestLoggingMiddleware.
    """
    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        logging_client().get("/echo")

    (record,) = records_of(caplog)
    assert record.getMessage() == REQUEST_LOG_MESSAGE
    assert (record.method, record.path, record.status) == ("GET", "/echo", 200)
    assert record.duration_ms >= 0


def test_when_a_route_crashes_then_the_access_line_still_reports_a_500(caplog):
    """when the application raises, the completion line is logged with status 500.

    Validates app.api.middleware.logging.RequestLoggingMiddleware.
    """
    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        logging_client().get("/crash")

    (record,) = records_of(caplog)
    assert record.status == HTTPStatus.INTERNAL_SERVER_ERROR


def test_when_request_has_a_query_body_and_client_then_none_is_logged(caplog):
    """when a request has a query string, a body and a client, none is logged.

    They hold tokens and personal data, so the access line records the path only.

    Validates app.api.middleware.logging.RequestLoggingMiddleware.
    """
    client = logging_client(client=(CLIENT_ADDRESS, 4000))

    with caplog.at_level(logging.DEBUG, logger=LOGGING_LOGGER):
        client.get("/echo", params={"search": QUERY_VALUE})
        client.post("/submit", json={"comment": BODY_VALUE})

    logged = " ".join(f"{vars(record)}" for record in caplog.records)
    for leaked in (QUERY_VALUE, BODY_VALUE, CLIENT_ADDRESS):
        assert leaked not in logged
    assert [record.path for record in records_of(caplog)] == ["/echo", "/submit"]


def test_when_requests_are_within_the_limit_then_remaining_quota_counts_down():
    """when requests stay under the limit, each response shows the quota left.

    Validates app.api.middleware.rate_limiting.RateLimitingMiddleware.
    """
    client = limited_client(FakeClock())

    remaining = [
        client.get("/echo").headers[REMAINING_HEADER] for _ in range(RATE_LIMIT)
    ]

    assert remaining == ["2", "1", "0"]
    assert client.get("/echo").headers[LIMIT_HEADER] == str(RATE_LIMIT)


def test_when_the_limit_is_exceeded_then_429_with_envelope_and_retry_headers():
    """when a client sends one request too many, it gets 429 and when to retry.

    Validates app.api.middleware.rate_limiting.RateLimitingMiddleware.
    """
    clock = FakeClock()
    client = limited_client(clock)
    exhaust_quota(client)
    clock.advance(10)

    response = client.get("/echo")

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    error = response.json()["error"]
    assert (error["code"], error["message"]) == (RATE_LIMITED_CODE, "Too many requests")
    assert error["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert response.headers[RETRY_AFTER_HEADER] == str(WINDOW_SECONDS - 10)
    assert response.headers[REMAINING_HEADER] == "0"
    assert response.headers[RESET_HEADER] == str(WINDOW_SECONDS - 10)


def test_when_the_window_has_passed_then_the_client_may_send_again():
    """when the whole window elapses, the quota is available again.

    Validates app.api.middleware.rate_limiting.RateLimitingMiddleware.
    """
    clock = FakeClock()
    client = limited_client(clock)
    exhaust_quota(client)
    assert client.get("/echo").status_code == HTTPStatus.TOO_MANY_REQUESTS

    clock.advance(WINDOW_SECONDS)

    assert client.get("/echo").status_code == HTTPStatus.OK


def test_when_requests_arrive_spread_out_then_the_window_slides():
    """when the oldest request leaves the window, one slot frees up at a time.

    Validates app.api.middleware.rate_limiting.RateLimitingMiddleware.
    """
    clock = FakeClock()
    client = limited_client(clock)
    for _ in range(RATE_LIMIT):
        client.get("/echo")
        clock.advance(WINDOW_SECONDS / RATE_LIMIT)

    statuses = [client.get("/echo").status_code for _ in range(2)]

    assert statuses == [200, 429]


def test_when_two_clients_share_the_server_then_each_has_its_own_quota():
    """when one client exhausts its quota, another client is unaffected.

    Validates app.api.middleware.rate_limiting.RateLimitingMiddleware.
    """
    clock = FakeClock()
    first_client = limited_client(clock, client_address="10.0.0.1")
    other_client = TestClient(first_client.app, client=("10.0.0.2", 5000))
    exhaust_quota(first_client)

    assert first_client.get("/echo").status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert other_client.get("/echo").status_code == HTTPStatus.OK


@pytest.mark.parametrize("path", EXEMPT_PATHS)
def test_when_a_health_path_is_requested_then_it_is_never_limited_or_counted(path):
    """when probes hit a health path, they never get 429 and use no quota.

    Validates app.api.middleware.rate_limiting.RateLimitingMiddleware.
    """
    client = limited_client(FakeClock())

    statuses = {client.get(path).status_code for _ in range(RATE_LIMIT * 3)}

    assert statuses == {HTTPStatus.OK}
    assert client.get("/echo").headers[REMAINING_HEADER] == str(RATE_LIMIT - 1)


def test_when_stale_clients_are_left_behind_then_their_buckets_are_swept():
    """when a window passes, a later request drops the buckets of idle clients.

    The sweep keeps memory bounded when many addresses each send one request.
    There is no public view of the buckets, so the private mapping is read.

    Validates app.api.middleware.rate_limiting.RateLimitingMiddleware.
    """
    clock = FakeClock()
    middleware = RateLimitingMiddleware(
        probe_app(), requests=RATE_LIMIT, window_seconds=WINDOW_SECONDS, clock=clock
    )
    for index in range(IDLE_CLIENT_COUNT):
        TestClient(middleware, client=(f"10.1.0.{index}", 5000)).get("/echo")
    assert len(middleware._arrivals) == IDLE_CLIENT_COUNT

    clock.advance(WINDOW_SECONDS * 2)
    TestClient(middleware, client=("10.2.0.1", 5000)).get("/echo")

    assert list(middleware._arrivals) == ["10.2.0.1"]


def test_when_a_response_is_built_then_it_carries_the_base_security_headers():
    """when any path is requested, every base security header is present and exact.

    Validates app.api.middleware.security.SecurityHeadersMiddleware.
    """
    response = secured_client(docs_enabled=False).get("/echo")

    for name, value in BASE_SECURITY_HEADERS.items():
        assert response.headers[name] == value


@pytest.mark.parametrize("docs_enabled", [True, False])
def test_when_a_response_is_built_then_it_never_announces_the_version(docs_enabled):
    """when a response is built, no header reveals the API version.

    Validates app.api.middleware.security.SecurityHeadersMiddleware.
    """
    headers = secured_client(docs_enabled=docs_enabled).get("/echo").headers

    assert "x-api-version" not in headers


@pytest.mark.parametrize("docs_enabled", [True, False])
@pytest.mark.parametrize("path", ["/echo", "/api/docs", "/docs-archive"])
def test_when_a_path_is_not_a_docs_path_then_the_strict_policy_applies(
    docs_enabled, path
):
    """when a non-docs path is requested, it gets the strict policy either way.

    Validates app.api.middleware.security.SecurityHeadersMiddleware.
    """
    response = secured_client(docs_enabled=docs_enabled).get(path)

    assert response.headers[CONTENT_SECURITY_POLICY_HEADER] == (
        API_CONTENT_SECURITY_POLICY
    )


@pytest.mark.parametrize("path", sorted(DOCS_PAGE_PATHS))
def test_when_docs_are_enabled_then_the_docs_pages_get_the_relaxed_policy(path):
    """when docs are served, each documentation page gets the CDN-friendly policy.

    Validates app.api.middleware.security.SecurityHeadersMiddleware.
    """
    response = secured_client(docs_enabled=True).get(path)

    assert response.headers[CONTENT_SECURITY_POLICY_HEADER] == (
        DOCS_CONTENT_SECURITY_POLICY
    )


def test_when_docs_are_enabled_then_the_openapi_schema_keeps_the_strict_policy():
    """when docs are served, the JSON schema still gets the strict policy.

    No browser renders the schema, so it needs no CDN allowance.

    Validates app.api.middleware.security.SecurityHeadersMiddleware.
    """
    response = secured_client(docs_enabled=True).get(OPENAPI_PATH)

    assert response.headers[CONTENT_SECURITY_POLICY_HEADER] == (
        API_CONTENT_SECURITY_POLICY
    )


@pytest.mark.parametrize("path", sorted(DOCS_PATHS))
def test_when_docs_are_disabled_then_even_the_docs_paths_get_the_strict_policy(path):
    """when docs are not served, the relaxed policy is never emitted.

    Validates app.api.middleware.security.SecurityHeadersMiddleware.
    """
    response = secured_client(docs_enabled=False).get(path)

    assert response.headers[CONTENT_SECURITY_POLICY_HEADER] == (
        API_CONTENT_SECURITY_POLICY
    )


def test_when_the_strict_policy_is_read_then_it_forbids_loading_and_framing():
    """when the API policy is inspected, it blocks all loads and all framing.

    Validates app.api.middleware.security.API_CONTENT_SECURITY_POLICY.
    """
    assert "default-src 'none'" in API_CONTENT_SECURITY_POLICY
    assert "frame-ancestors 'none'" in API_CONTENT_SECURITY_POLICY


def test_when_a_path_parameter_holds_text_then_the_route_template_is_logged(caplog):
    """when a route has a path parameter, the log names the template, not the value.

    A path parameter can hold user text, which must not reach the log pipeline.

    Validates app.api.middleware.logging.RequestLoggingMiddleware.
    """
    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        logging_client().get(f"/items/{SECRET_PATH_TEXT}")

    (record,) = records_of(caplog)
    assert record.path == ROUTE_TEMPLATE
    assert SECRET_PATH_TEXT not in str(vars(record))


def test_when_no_route_matches_then_the_log_uses_a_fixed_label(caplog):
    """when an unknown path is requested, the log holds a fixed label, not the path.

    The caller chooses an unmatched path, so it must not be logged raw.

    Validates app.api.middleware.logging.RequestLoggingMiddleware.
    """
    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        logging_client().get(f"/{SECRET_PATH_TEXT}")

    (record,) = records_of(caplog)
    assert record.path == UNMATCHED_ROUTE
    assert record.status == HTTPStatus.NOT_FOUND


def test_when_forwarded_for_is_spoofed_then_the_client_keeps_its_own_bucket():
    """when a client sends X-Forwarded-For, its quota stays keyed by its peer address.

    Uvicorn rewrites the peer address from that header only for trusted proxies;
    the limiter must never read the header itself.

    Validates app.api.middleware.rate_limiting.RateLimitingMiddleware.
    """
    client = limited_client(FakeClock())
    exhaust_quota(client)

    response = client.get("/echo", headers={"X-Forwarded-For": SPOOFED_FORWARDED_FOR})

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS


@pytest.mark.parametrize(
    ("first_address", "second_address", "shares_quota"),
    [
        pytest.param("2001:db8:1:2::1", "2001:db8:1:2:ffff::9", True, id="same-/64"),
        pytest.param("2001:db8:1:2::1", "2001:db8:1:3::1", False, id="other-/64"),
        pytest.param("::ffff:10.0.0.1", "10.0.0.1", True, id="ipv4-mapped"),
        pytest.param("10.0.0.1", "10.0.0.2", False, id="other-ipv4-address"),
    ],
)
def test_when_addresses_are_compared_then_ipv6_is_keyed_by_its_64_bit_prefix(
    first_address, second_address, shares_quota
):
    """when two addresses connect, they share a quota only when they are one client.

    One IPv6 subscriber holds a whole /64, so the full address is not a client.

    Validates app.api.middleware.rate_limiting.RateLimitingMiddleware.
    """
    first = limited_client(FakeClock(), client_address=first_address)
    exhaust_quota(first)

    second_status = (
        same_limiter_other_address(first, second_address).get("/echo").status_code
    )

    expected = HTTPStatus.TOO_MANY_REQUESTS if shares_quota else HTTPStatus.OK
    assert second_status == expected


def test_when_too_many_clients_are_tracked_then_the_longest_tracked_one_is_forgotten():
    """when the tracking cap is reached, the oldest client's quota starts over.

    Memory stays bounded under a scan of many addresses; the price is that the
    forgotten client gets a fresh window.

    Validates app.api.middleware.rate_limiting.RateLimitingMiddleware.
    """
    first = limited_client(
        FakeClock(),
        client_address="10.0.0.1",
        max_tracked_clients=TRACKED_CLIENT_CAP,
    )
    exhaust_quota(first)
    for address in ("10.0.0.2", "10.0.0.3"):
        same_limiter_other_address(first, address).get("/echo")

    response = first.get("/echo")

    assert response.status_code == HTTPStatus.OK
    assert response.headers[REMAINING_HEADER] == str(RATE_LIMIT - 1)


def test_when_a_response_is_built_then_the_legacy_xss_auditor_is_switched_off():
    """when any response is built, X-XSS-Protection is 0.

    The auditor can itself be abused; the CSP does the protecting.

    Validates app.api.middleware.security.SecurityHeadersMiddleware.
    """
    response = secured_client(docs_enabled=False).get("/echo")

    assert response.headers["X-XSS-Protection"] == "0"


def test_when_a_route_crashes_then_a_generic_500_envelope_with_the_request_id_is_sent():
    """when a route raises, the client gets the generic 500 envelope and the id.

    Validates app.api.middleware.unhandled_errors.UnhandledErrorMiddleware.
    """
    response = guarded_client().get("/crash")

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    error = response.json()["error"]
    assert (error["code"], error["message"]) == (
        INTERNAL_ERROR_CODE,
        GENERIC_SERVER_ERROR_MESSAGE,
    )
    assert error["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert CRASH_DETAIL not in response.text


def test_when_a_route_crashes_then_the_500_carries_the_security_headers():
    """when a route raises, the 500 still passes through the layers around it.

    Validates app.api.middleware.unhandled_errors.UnhandledErrorMiddleware.
    """
    response = guarded_client().get("/crash")

    for name, value in BASE_SECURITY_HEADERS.items():
        assert response.headers[name] == value


def test_when_a_route_crashes_then_the_exception_is_logged_once_with_the_request_id(
    caplog,
):
    """when a route raises, one record holds the traceback and the request id.

    A second record would mean the server logged the exception again.

    Validates app.api.middleware.unhandled_errors.UnhandledErrorMiddleware.
    """
    with caplog.at_level(logging.WARNING):
        response = guarded_client().get("/crash")

    (record,) = [item for item in caplog.records if item.exc_info]
    assert record.name == HANDLER_LOGGER
    assert record.getMessage() == UNEXPECTED_ERROR_LOG_MESSAGE
    assert record.request_id == response.headers[REQUEST_ID_HEADER]


def test_when_a_route_crashes_then_the_access_line_reports_the_500_that_was_sent(
    caplog,
):
    """when a route raises, the http.request line records the 500 of the response.

    Validates app.api.middleware.unhandled_errors.UnhandledErrorMiddleware.
    """
    with caplog.at_level(logging.INFO, logger=LOGGING_LOGGER):
        guarded_client().get("/crash")

    (record,) = records_of(caplog)
    assert record.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def fail_after_status_line(scope, receive, send) -> None:
    """ASGI application that starts a response and then raises."""
    await send({"type": "http.response.start", "status": 200, "headers": []})
    raise RuntimeError(CRASH_DETAIL)


async def test_when_the_response_has_started_then_no_second_response_is_sent(caplog):
    """when a route fails after its status line, the failure is logged and not answered.

    A second ``http.response.start`` would break the protocol, so the server must
    end the connection instead.

    Validates app.api.middleware.unhandled_errors.UnhandledErrorMiddleware.
    """
    with caplog.at_level(logging.ERROR):
        sent = await run_asgi(UnhandledErrorMiddleware(fail_after_status_line))

    assert [message["type"] for message in sent] == ["http.response.start"]
    assert [record.getMessage() for record in caplog.records] == [
        UNEXPECTED_ERROR_LOG_MESSAGE
    ]


async def test_when_the_task_is_cancelled_then_the_cancellation_propagates():
    """when the request is cancelled, the catch-all does not swallow the cancellation.

    Validates app.api.middleware.unhandled_errors.UnhandledErrorMiddleware.
    """

    async def cancelled(scope, receive, send) -> None:
        """ASGI application that is cancelled."""
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await run_asgi(UnhandledErrorMiddleware(cancelled))


async def test_when_the_scope_is_not_http_then_the_exception_is_not_caught():
    """when a lifespan connection fails, the error reaches the server unchanged.

    Validates app.api.middleware.unhandled_errors.UnhandledErrorMiddleware.
    """

    async def failing(scope, receive, send) -> None:
        """ASGI application that fails."""
        raise RuntimeError(CRASH_DETAIL)

    with pytest.raises(RuntimeError, match=CRASH_DETAIL):
        await run_asgi(UnhandledErrorMiddleware(failing), scope_type="lifespan")


async def test_when_the_peer_address_is_unknown_then_those_requests_share_one_bucket():
    """when a connection has no client address, its requests are still counted.

    Validates app.api.middleware.rate_limiting.RateLimitingMiddleware.
    """

    async def answer_ok(scope, receive, send) -> None:
        """ASGI application that always answers 200."""
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    limiter = RateLimitingMiddleware(
        answer_ok, requests=1, window_seconds=WINDOW_SECONDS, clock=FakeClock()
    )

    first = await run_asgi(limiter)
    second = await run_asgi(limiter)

    assert first[0]["status"] == HTTPStatus.OK
    assert second[0]["status"] == HTTPStatus.TOO_MANY_REQUESTS
