"""Turns exceptions into responses that carry the error envelope.

Four handlers cover everything: domain errors, request validation failures,
framework HTTP errors and anything unexpected. The HTTP status of each domain
error lives in ``DOMAIN_ERROR_MAPPINGS``, the only place that knows about it, so
the domain layer stays free of HTTP. Responses never echo submitted values or
exception text: details go to the logs, the client gets a stable code and a
message written for it.

Starlette re-raises an exception after its server-error handler has answered it,
which makes the ASGI server log it a second time and sends the response from
outside every middleware. ``UnhandledErrorMiddleware`` therefore answers
unexpected errors from inside the middleware stack, with the two functions below;
the registered ``Exception`` handler is only the fallback for an application
built without that middleware.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from types import MappingProxyType

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import error_response, request_id_of, route_template
from app.api.headers import RETRY_AFTER_HEADER, WWW_AUTHENTICATE_HEADER
from app.api.schemas.errors import FieldError
from app.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    DomainValidationError,
    EntityNotFoundError,
    ExternalServiceError,
)
from app.infrastructure.errors import DatabaseOperationError

logger = logging.getLogger(__name__)

SERVICE_UNAVAILABLE_RETRY_AFTER_SECONDS = 30
VALIDATION_ERROR_CODE = "VALIDATION_ERROR"
VALIDATION_ERROR_MESSAGE = "The request failed validation"
INTERNAL_ERROR_CODE = "INTERNAL_SERVER_ERROR"
GENERIC_SERVER_ERROR_MESSAGE = "An unexpected error occurred"
BEARER_CHALLENGE = "Bearer"


@dataclass(frozen=True)
class ErrorMapping:
    """How one kind of domain error is answered and logged.

    Attributes:
        status_code: HTTP status of the response.
        log_level: Severity of the log record. Client mistakes log low, while
            failures that need an operator's attention log high.
        headers: Extra response headers.
    """

    status_code: int
    log_level: int
    headers: Mapping[str, str] = field(default_factory=dict)


DOMAIN_ERROR_MAPPINGS: Mapping[type[DomainError], ErrorMapping] = MappingProxyType(
    {
        DomainValidationError: ErrorMapping(
            status.HTTP_422_UNPROCESSABLE_CONTENT, logging.INFO
        ),
        EntityNotFoundError: ErrorMapping(status.HTTP_404_NOT_FOUND, logging.INFO),
        ConflictError: ErrorMapping(status.HTTP_409_CONFLICT, logging.INFO),
        AuthenticationError: ErrorMapping(
            status.HTTP_401_UNAUTHORIZED,
            logging.WARNING,
            {WWW_AUTHENTICATE_HEADER: BEARER_CHALLENGE},
        ),
        AuthorizationError: ErrorMapping(status.HTTP_403_FORBIDDEN, logging.WARNING),
        ExternalServiceError: ErrorMapping(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            logging.ERROR,
            {RETRY_AFTER_HEADER: str(SERVICE_UNAVAILABLE_RETRY_AFTER_SECONDS)},
        ),
        DatabaseOperationError: ErrorMapping(
            status.HTTP_500_INTERNAL_SERVER_ERROR, logging.ERROR
        ),
    }
)

# A DomainError subclass nobody mapped is still the caller's problem, not a crash.
FALLBACK_DOMAIN_MAPPING = ErrorMapping(status.HTTP_400_BAD_REQUEST, logging.WARNING)


def resolve_mapping(error_type: type[DomainError]) -> ErrorMapping:
    """Find the mapping for a domain error class.

    Walks the class hierarchy so a subclass, such as a circuit-open error, is
    answered like the nearest mapped ancestor.

    Args:
        error_type: Class of the raised error.

    Returns:
        The mapping of the nearest mapped ancestor, or ``FALLBACK_DOMAIN_MAPPING``
        when none of its ancestors is mapped.
    """
    for candidate in error_type.__mro__:
        mapping = DOMAIN_ERROR_MAPPINGS.get(candidate)
        if mapping is not None:
            return mapping
    return FALLBACK_DOMAIN_MAPPING


def _field_path(location: tuple[int | str, ...]) -> str:
    # The first element only names where the value came from (body, query, header).
    path = location[1:] or location
    return ".".join(str(part) for part in path)


def _field_errors(exc: RequestValidationError) -> list[FieldError]:
    # Pydantic's ``input`` and ``ctx`` entries can hold the submitted value, so
    # only the location and the message are read.
    return [
        FieldError(field=_field_path(tuple(error["loc"])), message=error["msg"])
        for error in exc.errors()
    ]


async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    """Answer a domain error with its mapped status and public message.

    Args:
        request: The failed request.
        exc: The raised ``DomainError``.

    Returns:
        An error envelope response. Diagnostic context goes to the log only.
    """
    mapping = resolve_mapping(type(exc))
    logger.log(
        mapping.log_level,
        "request.domain_error",
        extra={
            "error_code": exc.error_code,
            "path": route_template(request.scope),
            "method": request.method,
            "context": exc.log_context,
        },
    )
    return error_response(
        mapping.status_code,
        exc.error_code,
        exc.public_message,
        request_id=request_id_of(request),
        headers=mapping.headers,
    )


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Answer a failed request validation with 422 and per-field messages.

    Args:
        request: The failed request.
        exc: The raised ``RequestValidationError``.

    Returns:
        An error envelope listing field paths and messages, never the input.
    """
    details = _field_errors(exc)
    logger.info(
        "request.validation_failed",
        extra={
            "path": route_template(request.scope),
            "method": request.method,
            "fields": [item.field for item in details],
        },
    )
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        VALIDATION_ERROR_CODE,
        VALIDATION_ERROR_MESSAGE,
        request_id=request_id_of(request),
        details=details,
    )


async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Answer a framework HTTP error, keeping the headers it carries.

    Args:
        request: The failed request.
        exc: The raised HTTP exception, for example an unknown route (404) or a
            wrong method (405, which carries ``Allow``).

    Returns:
        An error envelope response. A 5xx status gets a generic message, since
        the exception detail may describe internals.
    """
    is_server_error = exc.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
    logger.log(
        logging.ERROR if is_server_error else logging.INFO,
        "request.http_error",
        extra={
            "status": exc.status_code,
            "path": route_template(request.scope),
            "method": request.method,
        },
    )
    message = GENERIC_SERVER_ERROR_MESSAGE if is_server_error else str(exc.detail)
    return error_response(
        exc.status_code,
        f"HTTP_{exc.status_code}",
        message,
        request_id=request_id_of(request),
        headers=exc.headers,
    )


def log_unexpected_error(request: Request, exc: Exception) -> None:
    """Write the one log record of an unexpected exception.

    Args:
        request: The failed request.
        exc: The raised exception. Its text and traceback go to the log only.
    """
    # The request id is passed explicitly: when Starlette's outermost layer
    # answers, the logging middleware has already reset its context variable.
    logger.error(
        "request.unhandled_exception",
        exc_info=exc,
        extra={
            "path": route_template(request.scope),
            "method": request.method,
            "request_id": request_id_of(request),
        },
    )


def unexpected_error_response(request: Request) -> JSONResponse:
    """Build the generic 500 that reveals nothing about the failure.

    Args:
        request: The failed request.

    Returns:
        An error envelope response carrying the request id.
    """
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        INTERNAL_ERROR_CODE,
        GENERIC_SERVER_ERROR_MESSAGE,
        request_id=request_id_of(request),
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Answer any unhandled exception with a generic 500.

    Args:
        request: The failed request.
        exc: The raised exception. Its text and traceback go to the log only.

    Returns:
        An error envelope response that reveals nothing about the failure.
    """
    log_unexpected_error(request, exc)
    return unexpected_error_response(request)


def setup_exception_handlers(app: FastAPI) -> None:
    """Register the four handlers on the application.

    The ``Exception`` handler only answers errors that no
    ``UnhandledErrorMiddleware`` caught first.

    Args:
        app: The application to configure.
    """
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)
