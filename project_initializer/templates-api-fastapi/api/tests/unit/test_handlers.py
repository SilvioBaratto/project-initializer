"""Unit tests for the exception handlers and the error envelope they produce."""

import logging
from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import pytest
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.api.handlers import (
    DOMAIN_ERROR_MAPPINGS,
    FALLBACK_DOMAIN_MAPPING,
    GENERIC_SERVER_ERROR_MESSAGE,
    SERVICE_UNAVAILABLE_RETRY_AFTER_SECONDS,
    resolve_mapping,
    setup_exception_handlers,
)
from app.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    DomainValidationError,
    EntityNotFoundError,
    ExternalServiceError,
)
from app.infrastructure.errors import (
    CircuitOpenError,
    DatabaseOperationError,
    DatabaseUnavailableError,
)

pytestmark = pytest.mark.unit

HANDLER_LOGGER = "app.api.handlers"
REQUEST_ID = "req-4711"
SUBMITTED_VALUE = "value-that-must-not-be-echoed"
INTERNAL_DETAIL = "connection to db-internal-7 refused"
SQLSTATE_OF_FAILURE = "42703"
SECRET_PATH_TEXT = "path-text-that-must-not-be-logged"
SHORT_NAME_LIMIT = 5

DOMAIN_RESPONSES = [
    pytest.param(
        DomainValidationError("Name is blank"), 422, "VALIDATION_ERROR", id="validation"
    ),
    pytest.param(EntityNotFoundError("Item"), 404, "NOT_FOUND", id="not-found"),
    pytest.param(ConflictError(), 409, "CONFLICT", id="conflict"),
    pytest.param(AuthenticationError(), 401, "AUTHENTICATION_ERROR", id="authn"),
    pytest.param(AuthorizationError(), 403, "AUTHORIZATION_ERROR", id="authz"),
    pytest.param(ExternalServiceError(), 503, "SERVICE_UNAVAILABLE", id="external"),
    pytest.param(CircuitOpenError(), 503, "SERVICE_UNAVAILABLE", id="circuit-open"),
    pytest.param(
        DatabaseUnavailableError(), 503, "SERVICE_UNAVAILABLE", id="database-down"
    ),
    pytest.param(DatabaseOperationError(), 500, "DATABASE_ERROR", id="database-fault"),
]
LOG_LEVELS = [
    pytest.param(DomainValidationError(), logging.INFO, id="validation"),
    pytest.param(EntityNotFoundError("Item"), logging.INFO, id="not-found"),
    pytest.param(ConflictError(), logging.INFO, id="conflict"),
    pytest.param(AuthenticationError(), logging.WARNING, id="authn"),
    pytest.param(AuthorizationError(), logging.WARNING, id="authz"),
    pytest.param(ExternalServiceError(), logging.ERROR, id="external"),
    pytest.param(DatabaseOperationError(), logging.ERROR, id="database-fault"),
]


class UnmappedDomainError(DomainError):
    """A domain error that no mapping names."""


class SubmittedBody(BaseModel):
    """Body model with bounds, for the validation-failure tests."""

    name: str = Field(max_length=SHORT_NAME_LIMIT)
    count: int


class FixedRequestId:
    """ASGI wrapper that plays the part of the request-logging middleware."""

    def __init__(self, app: Callable[..., Any]) -> None:
        self._app = app

    async def __call__(self, scope, receive, send) -> None:
        """Attach a known request id to the request state, then continue."""
        scope.setdefault("state", {})["request_id"] = REQUEST_ID
        await self._app(scope, receive, send)


def build_client(
    exception: BaseException | None = None, *, request_id: bool = False
) -> TestClient:
    """A client for a small application with the handlers and a few routes.

    Server exceptions are returned as responses instead of being re-raised, so a
    test can inspect the 500 the handler produced.

    Args:
        exception: What ``GET /raise`` raises.
        request_id: Whether a stand-in for the logging middleware assigns an id.
    """
    application = FastAPI()
    setup_exception_handlers(application)
    if request_id:
        application.add_middleware(FixedRequestId)

    @application.get("/raise")
    def raise_given_exception() -> None:
        """Raise the exception the test supplied."""
        raise exception

    @application.post("/body")
    def take_body(body: SubmittedBody) -> None:
        """Accept a bounded body."""

    @application.get("/query")
    def take_query(limit: int = Query(ge=1)) -> None:
        """Accept a bounded query parameter."""

    @application.get("/header")
    def take_header(x_token: str = Header(pattern="^[a-z]+$")) -> None:
        """Accept a patterned header."""

    return TestClient(application, raise_server_exceptions=False)


def get_raising(exception: BaseException, **client_options: Any):
    """Request a route that raises ``exception`` and return the response."""
    return build_client(exception, **client_options).get("/raise")


@pytest.mark.parametrize(("exception", "status_code", "code"), DOMAIN_RESPONSES)
def test_when_domain_error_is_raised_then_its_mapped_status_and_code_are_returned(
    exception, status_code, code
):
    """when a domain error escapes a route, the response carries its status and code.

    Validates app.api.handlers.handle_domain_error().
    """
    response = get_raising(exception)

    assert response.status_code == status_code
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"] == exception.public_message
    assert {"code", "message", "timestamp"} <= set(error)


def test_when_error_is_not_mapped_then_the_fallback_status_is_used():
    """when a domain error has no mapped ancestor, the response is a 400.

    Validates app.api.handlers.resolve_mapping().
    """
    response = get_raising(UnmappedDomainError())

    assert response.status_code == FALLBACK_DOMAIN_MAPPING.status_code
    assert resolve_mapping(UnmappedDomainError) is FALLBACK_DOMAIN_MAPPING


def test_when_subclass_is_raised_then_the_nearest_mapped_ancestor_decides():
    """when an infrastructure error subclasses a mapped error, it takes that mapping.

    Validates app.api.handlers.resolve_mapping().
    """
    assert (
        resolve_mapping(CircuitOpenError) is DOMAIN_ERROR_MAPPINGS[ExternalServiceError]
    )


@pytest.mark.parametrize(
    "error_type",
    [ExternalServiceError, DatabaseOperationError],
    ids=["outage", "fault"],
)
def test_when_domain_error_has_log_context_then_the_client_never_sees_it(error_type):
    """when a domain error carries diagnostic context, none of it is in the response.

    Validates app.api.handlers.handle_domain_error().
    """
    error = error_type(
        log_context={"dsn": INTERNAL_DETAIL, "sqlstate": SQLSTATE_OF_FAILURE}
    )

    response = get_raising(error)

    for leaked in (INTERNAL_DETAIL, "dsn", SQLSTATE_OF_FAILURE):
        assert leaked not in response.text


@pytest.mark.parametrize(("exception", "level"), LOG_LEVELS)
def test_when_domain_error_is_handled_then_it_is_logged_with_context_at_its_level(
    caplog, exception, level
):
    """when a domain error is answered, one record keeps the level and the context.

    Validates app.api.handlers.handle_domain_error().
    """
    exception.log_context["reason"] = "diagnostic"

    with caplog.at_level(logging.DEBUG, logger=HANDLER_LOGGER):
        get_raising(exception)

    (record,) = [item for item in caplog.records if item.name == HANDLER_LOGGER]
    assert record.levelno == level
    assert record.error_code == exception.error_code
    assert record.context == {"reason": "diagnostic"}


def test_when_authentication_fails_then_the_response_names_the_bearer_scheme():
    """when authentication fails, a 401 carries the WWW-Authenticate challenge.

    Validates app.api.handlers.DOMAIN_ERROR_MAPPINGS.
    """
    response = get_raising(AuthenticationError())

    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_when_a_dependency_is_down_then_the_response_says_when_to_retry():
    """when a required service is unavailable, a 503 carries Retry-After.

    Validates app.api.handlers.DOMAIN_ERROR_MAPPINGS.
    """
    response = get_raising(ExternalServiceError())

    assert response.headers["Retry-After"] == str(
        SERVICE_UNAVAILABLE_RETRY_AFTER_SECONDS
    )


@pytest.mark.parametrize(
    "exception",
    [
        DomainValidationError(),
        EntityNotFoundError("Item"),
        ConflictError(),
        AuthorizationError(),
        DatabaseOperationError(),
    ],
    ids=["validation", "not-found", "conflict", "authz", "database-fault"],
)
def test_when_error_is_not_auth_or_outage_then_no_challenge_headers_are_sent(exception):
    """when a 4xx other than 401 is answered, no challenge or retry header appears.

    Validates app.api.handlers.handle_domain_error().
    """
    headers = get_raising(exception).headers

    assert "www-authenticate" not in headers
    assert "retry-after" not in headers


def test_when_body_is_invalid_then_each_field_is_listed_without_its_value():
    """when a body breaks its bounds, 422 names the fields and never echoes values.

    Validates app.api.handlers.handle_validation_error().
    """
    client = build_client()

    response = client.post("/body", json={"name": SUBMITTED_VALUE, "count": "many"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert {detail["field"] for detail in error["details"]} == {"name", "count"}
    assert SUBMITTED_VALUE not in response.text
    assert "many" not in response.text


def test_when_query_and_header_are_invalid_then_the_source_prefix_is_dropped():
    """when a query or header value is invalid, the field path starts at its name.

    Validates app.api.handlers.handle_validation_error().
    """
    client = build_client()

    query_fields = client.get("/query", params={"limit": 0}).json()["error"]["details"]
    header_fields = client.get("/header", headers={"X-Token": "A1"}).json()["error"][
        "details"
    ]

    assert [detail["field"] for detail in query_fields] == ["limit"]
    assert [detail["field"] for detail in header_fields] == ["x-token"]


def test_when_body_is_not_json_then_422_is_returned_without_the_raw_text():
    """when the body cannot be parsed, 422 is returned and the text is not repeated.

    Validates app.api.handlers.handle_validation_error().
    """
    client = build_client()

    response = client.post(
        "/body",
        content=f"{{broken {SUBMITTED_VALUE}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert SUBMITTED_VALUE not in response.text


def test_when_route_is_unknown_then_a_404_envelope_is_returned():
    """when no route matches, the framework 404 is wrapped in the envelope.

    Validates app.api.handlers.handle_http_exception().
    """
    response = build_client().get("/missing")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "HTTP_404"


def test_when_method_is_not_allowed_then_the_allow_header_is_kept():
    """when a route is called with the wrong method, 405 keeps the Allow header.

    Validates app.api.handlers.handle_http_exception().
    """
    response = build_client().delete("/body")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert "POST" in response.headers["Allow"]


def test_when_http_exception_carries_headers_then_they_are_forwarded():
    """when an HTTPException sets a header, the response keeps it.

    Validates app.api.handlers.handle_http_exception().
    """
    exception = HTTPException(401, "nope", headers={"WWW-Authenticate": "Bearer"})

    response = get_raising(exception)

    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_when_client_error_has_a_detail_then_it_is_the_message():
    """when a 4xx HTTPException has a detail, the detail becomes the message.

    Validates app.api.handlers.handle_http_exception().
    """
    response = get_raising(HTTPException(418, "short and stout"))

    assert response.json()["error"]["message"] == "short and stout"


@pytest.mark.parametrize("status_code", [500, 502, 503])
def test_when_server_error_has_a_detail_then_the_message_is_generic(status_code):
    """when a 5xx HTTPException carries internals, the response hides them.

    Validates app.api.handlers.handle_http_exception().
    """
    response = get_raising(HTTPException(status_code, INTERNAL_DETAIL))

    assert response.status_code == status_code
    assert response.json()["error"]["message"] == GENERIC_SERVER_ERROR_MESSAGE
    assert INTERNAL_DETAIL not in response.text


def test_when_unexpected_exception_is_raised_then_the_500_reveals_nothing():
    """when a route crashes, the body has no exception text, class or traceback.

    Validates app.api.handlers.handle_unexpected_error().
    """
    response = get_raising(RuntimeError(INTERNAL_DETAIL))

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert response.json()["error"]["message"] == GENERIC_SERVER_ERROR_MESSAGE
    for leaked in (INTERNAL_DETAIL, "RuntimeError", "Traceback"):
        assert leaked not in response.text


def test_when_unexpected_exception_is_raised_then_the_traceback_is_logged(caplog):
    """when a route crashes, the log record keeps the exception for operators.

    Validates app.api.handlers.handle_unexpected_error().
    """
    crash = RuntimeError(INTERNAL_DETAIL)

    with caplog.at_level(logging.ERROR, logger=HANDLER_LOGGER):
        get_raising(crash)

    (record,) = [item for item in caplog.records if item.name == HANDLER_LOGGER]
    assert record.exc_info[1] is crash


def test_when_unexpected_exception_is_raised_then_the_record_carries_the_request_id(
    caplog,
):
    """when the fallback handler answers, its log record names the request id.

    The id is passed explicitly because the server-error layer answers after the
    logging middleware has reset its context variable.

    Validates app.api.handlers.handle_unexpected_error().
    """
    with caplog.at_level(logging.ERROR, logger=HANDLER_LOGGER):
        get_raising(RuntimeError(INTERNAL_DETAIL), request_id=True)

    (record,) = [item for item in caplog.records if item.name == HANDLER_LOGGER]
    assert record.request_id == REQUEST_ID


def test_when_a_handled_error_is_logged_then_the_route_template_replaces_the_raw_path(
    caplog,
):
    """when a domain error is logged, a path parameter's text stays out of the record.

    Validates app.api.handlers.handle_domain_error().
    """
    application = FastAPI()
    setup_exception_handlers(application)

    @application.get("/things/{name}")
    def read_thing(name: str) -> None:
        """Fail as if the thing did not exist."""
        raise EntityNotFoundError("Thing")

    with caplog.at_level(logging.INFO, logger=HANDLER_LOGGER):
        TestClient(application).get(f"/things/{SECRET_PATH_TEXT}")

    (record,) = [item for item in caplog.records if item.name == HANDLER_LOGGER]
    assert record.path == "/things/{name}"
    assert SECRET_PATH_TEXT not in str(vars(record))


@pytest.mark.parametrize(
    "exception",
    [EntityNotFoundError("Item"), RuntimeError("boom"), HTTPException(404, "gone")],
    ids=["domain", "unexpected", "http"],
)
def test_when_request_has_an_id_then_every_error_body_repeats_it(exception):
    """when the logging middleware set a request id, each handler puts it in the body.

    Validates app.api.errors.request_id_of().
    """
    response = get_raising(exception, request_id=True)

    assert response.json()["error"]["request_id"] == REQUEST_ID


def test_when_request_has_no_id_then_the_field_is_left_out():
    """when no middleware set a request id, the body omits request_id.

    Validates app.api.errors.request_id_of().
    """
    response = get_raising(ConflictError())

    assert "request_id" not in response.json()["error"]
