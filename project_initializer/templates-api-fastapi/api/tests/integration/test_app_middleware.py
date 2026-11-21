"""Integration tests of the middleware stack as ``create_application`` assembles it.

The layers are exercised one by one in ``tests/unit/test_middleware.py``; these
tests cover what only the real composition shows: the order, the CORS interplay
with the limiter and with a crashing route, and the production-only limiter.
"""

import logging
import re
from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.api.handlers import INTERNAL_ERROR_CODE
from app.api.headers import REMAINING_HEADER, REQUEST_ID_HEADER, RETRY_AFTER_HEADER
from app.api.middleware.logging import RequestLoggingMiddleware
from app.api.middleware.rate_limiting import RateLimitingMiddleware
from app.api.middleware.security import (
    API_CONTENT_SECURITY_POLICY,
    CONTENT_SECURITY_POLICY_HEADER,
    SecurityHeadersMiddleware,
)
from app.api.middleware.unhandled_errors import UnhandledErrorMiddleware

pytestmark = pytest.mark.integration

GENERATED_ID = re.compile(r"^[0-9a-f]{32}$")
WINDOW_SECONDS = 60
TRUSTED_ORIGIN = "https://app.example.test"
CRASH_PATH = "/crash"
CRASH_DETAIL = "route failure"
UNEXPECTED_ERROR_LOG_MESSAGE = "request.unhandled_exception"
PRODUCTION_LIKE_ENVIRONMENTS = ["staging", "production"]
LOCAL_ENVIRONMENTS = ["development", "test"]
ALWAYS_PRESENT_LAYERS = [
    CORSMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    UnhandledErrorMiddleware,
]


@pytest.fixture
def ping_path(api_prefix: str) -> str:
    """URL of a public route that needs no database."""
    return f"{api_prefix}/test/ping"


@pytest.fixture
def crashing_app(build_app) -> Callable[..., FastAPI]:
    """Factory of a real application that also has a route which always raises.

    Routes added before the first request are part of the stack the request
    runs through, so the crash passes every real middleware layer.
    """

    def build(**overrides: Any) -> FastAPI:
        """Build the application under ``overrides`` plus the crashing route."""
        application = build_app(cors_origins=TRUSTED_ORIGIN, **overrides)

        @application.get(CRASH_PATH)
        def crash() -> None:
            """Fail with an unhandled exception."""
            raise RuntimeError(CRASH_DETAIL)

        return application

    return build


@pytest.fixture
def limited_production_client(build_app) -> Callable[..., TestClient]:
    """Factory of a client for a production-like app that allows one request."""

    def build(**overrides: Any) -> TestClient:
        """Build the app with a quota of one request and a known CORS origin."""
        application = build_app(
            environment="production",
            rate_limit_requests=1,
            rate_limit_window=WINDOW_SECONDS,
            cors_origins=TRUSTED_ORIGIN,
            **overrides,
        )
        return TestClient(application)

    return build


@pytest.mark.parametrize("environment", PRODUCTION_LIKE_ENVIRONMENTS)
def test_when_the_application_is_production_like_then_the_middleware_order_is_fixed(
    build_app, environment
):
    """when staging or production settings build the app, five layers wrap it in order.

    CORS is outermost so its headers reach 429 responses and preflights skip the
    limiter. The catch-all sits inside logging, security headers and CORS, so the
    500 it sends carries their headers, and outside the limiter.

    Validates app.main.create_application().
    """
    application = build_app(environment=environment)

    assert [layer.cls for layer in application.user_middleware] == [
        *ALWAYS_PRESENT_LAYERS,
        RateLimitingMiddleware,
    ]


@pytest.mark.parametrize("environment", LOCAL_ENVIRONMENTS)
def test_when_the_application_is_local_then_there_is_no_rate_limiter(
    build_app, environment
):
    """when a local environment builds the app, the limiter is not installed.

    Validates app.main.create_application().
    """
    application = build_app(environment=environment)

    assert [layer.cls for layer in application.user_middleware] == (
        ALWAYS_PRESENT_LAYERS
    )


def test_when_a_cross_origin_request_is_rejected_for_rate_then_cors_headers_are_present(
    limited_production_client, ping_path
):
    """when a browser client is rate limited, the 429 still carries CORS headers.

    Without them the browser hides the 429 behind an opaque CORS error.

    Validates app.main.create_application().
    """
    client = limited_production_client()
    headers = {"Origin": TRUSTED_ORIGIN}
    assert client.get(ping_path, headers=headers).status_code == HTTPStatus.OK

    response = client.get(ping_path, headers=headers)

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert response.headers["access-control-allow-origin"] == TRUSTED_ORIGIN
    assert RETRY_AFTER_HEADER in response.headers["access-control-expose-headers"]


def test_when_a_preflight_is_sent_then_it_does_not_consume_rate_limit_quota(
    limited_production_client, ping_path
):
    """when many preflights precede a real request, the real request is still allowed.

    Validates app.main.create_application().
    """
    client = limited_production_client()
    preflight_headers = {
        "Origin": TRUSTED_ORIGIN,
        "Access-Control-Request-Method": "GET",
    }

    preflight_statuses = {
        client.options(ping_path, headers=preflight_headers).status_code
        for _ in range(3)
    }
    real = client.get(ping_path, headers={"Origin": TRUSTED_ORIGIN})

    assert preflight_statuses == {HTTPStatus.OK}
    assert real.status_code == HTTPStatus.OK
    assert real.headers[REMAINING_HEADER] == "0"


def test_when_an_origin_is_not_configured_then_cors_headers_are_not_granted(
    limited_production_client, ping_path
):
    """when the Origin is not in the allow list, no allow-origin header is returned.

    Validates app.main.create_application().
    """
    response = limited_production_client().get(
        ping_path, headers={"Origin": "https://evil.example.test"}
    )

    assert "access-control-allow-origin" not in response.headers


def test_when_a_credentialed_request_is_made_then_cors_does_not_allow_credentials(
    limited_production_client, ping_path
):
    """when an allowed origin calls, the response never allows credentials.

    The API authenticates with a bearer header, so cookies never need to cross.

    Validates app.main.create_application().
    """
    response = limited_production_client().get(
        ping_path, headers={"Origin": TRUSTED_ORIGIN}
    )

    assert "access-control-allow-credentials" not in response.headers


def test_when_a_preflight_asks_for_patch_then_it_is_refused(
    limited_production_client, ping_path
):
    """when a preflight asks for PATCH, the API refuses it: no route uses it.

    Validates app.main.create_application().
    """
    response = limited_production_client().options(
        ping_path,
        headers={
            "Origin": TRUSTED_ORIGIN,
            "Access-Control-Request-Method": "PATCH",
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_when_the_real_app_serves_a_request_then_it_has_an_id_and_security_headers(
    build_app, ping_path
):
    """when the real app answers, the id and security headers come from the middleware.

    Validates app.main.create_application().
    """
    response = TestClient(build_app(environment="production")).get(ping_path)

    assert GENERATED_ID.fullmatch(response.headers[REQUEST_ID_HEADER])
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers[CONTENT_SECURITY_POLICY_HEADER] == (
        API_CONTENT_SECURITY_POLICY
    )


def test_when_a_route_crashes_then_the_500_carries_request_id_security_and_cors_headers(
    crashing_app,
):
    """when a route raises, the 500 has every header the outer layers add.

    Starlette's own server-error layer sits outside the middleware, so without the
    catch-all this 500 would carry none of them and a browser would hide it behind
    a CORS error. The client re-raises server exceptions, so reaching the
    assertions also proves the exception was not re-raised to the server.

    Validates app.main.create_application().
    """
    client = TestClient(crashing_app())

    response = client.get(CRASH_PATH, headers={"Origin": TRUSTED_ORIGIN})

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.json()["error"]["code"] == INTERNAL_ERROR_CODE
    assert response.json()["error"]["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert response.headers["access-control-allow-origin"] == TRUSTED_ORIGIN
    assert response.headers[CONTENT_SECURITY_POLICY_HEADER] == (
        API_CONTENT_SECURITY_POLICY
    )
    assert CRASH_DETAIL not in response.text


def test_when_a_route_crashes_then_the_application_logs_the_failure_once(
    crashing_app, caplog
):
    """when a route raises, one record carries the traceback; the server adds none.

    Validates app.main.create_application().
    """
    client = TestClient(crashing_app())

    with caplog.at_level(logging.WARNING):
        client.get(CRASH_PATH)

    with_traceback = [record for record in caplog.records if record.exc_info]
    assert [record.getMessage() for record in with_traceback] == [
        UNEXPECTED_ERROR_LOG_MESSAGE
    ]
