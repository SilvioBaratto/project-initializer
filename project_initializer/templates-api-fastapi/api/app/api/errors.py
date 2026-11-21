"""Builders for the error envelope, shared by handlers, middleware and routes."""

from collections.abc import Mapping
from datetime import UTC, datetime
from http import HTTPStatus
from types import MappingProxyType
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.types import Scope

from app.api.schemas.errors import ErrorBody, ErrorEnvelope, FieldError

UNMATCHED_ROUTE = "unmatched"

DEFAULT_ERROR_DESCRIPTIONS: Mapping[int, str] = MappingProxyType(
    {
        status.HTTP_400_BAD_REQUEST: "The request could not be processed",
        status.HTTP_401_UNAUTHORIZED: "Credentials are missing or invalid",
        status.HTTP_403_FORBIDDEN: "The caller lacks the required permission",
        status.HTTP_404_NOT_FOUND: "The resource does not exist",
        status.HTTP_409_CONFLICT: "The request conflicts with the current state",
        status.HTTP_422_UNPROCESSABLE_CONTENT: "The request failed validation",
        status.HTTP_429_TOO_MANY_REQUESTS: "Too many requests; retry after a pause",
        status.HTTP_503_SERVICE_UNAVAILABLE: "A required service is unavailable",
    }
)


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    request_id: str | None = None,
    details: list[FieldError] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build a JSON response holding an ``ErrorEnvelope``.

    Args:
        status_code: HTTP status of the response.
        code: Stable machine-readable error code.
        message: Text that is safe to show to an end user.
        request_id: Correlation id of the request, when known.
        details: Per-field problems of a validation failure.
        headers: Extra response headers, for example ``Retry-After``.

    Returns:
        The response. Fields that are None are left out of the body.
    """
    envelope = ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=message,
            timestamp=datetime.now(UTC),
            request_id=request_id,
            details=details,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json", exclude_none=True),
        headers=dict(headers) if headers else None,
    )


def error_responses(
    *status_codes: int, descriptions: Mapping[int, str] | None = None
) -> dict[int | str, dict[str, Any]]:
    """Describe error statuses for a route's ``responses=`` argument.

    Every entry is documented with ``ErrorEnvelope``, so the OpenAPI schema shows
    the body clients actually receive, including for 422.

    Args:
        *status_codes: Statuses the route can answer with.
        descriptions: Per-status text that replaces the default description.

    Returns:
        A mapping that can be passed as ``responses=``. A status without a
        default or custom description falls back to its standard HTTP phrase.
    """
    texts = {**DEFAULT_ERROR_DESCRIPTIONS, **(descriptions or {})}
    return {
        code: {
            "model": ErrorEnvelope,
            "description": texts.get(code) or HTTPStatus(code).phrase,
        }
        for code in status_codes
    }


AUTHENTICATED_ROUTE_ERRORS = error_responses(
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_503_SERVICE_UNAVAILABLE,
)
"""Statuses of every route that needs a caller identity, in any auth variant.

401 and 403 come from the credential check (the Entra variant also answers 403
for a missing scope); 503 from an identity provider that cannot be reached.
Merge it with the route's own statuses, for example
``{**AUTHENTICATED_ROUTE_ERRORS, **error_responses(404)}``.
"""


def route_template(scope: Scope) -> str:
    """Name the route that served a request, for logs.

    A path parameter can hold user text and an unmatched path is chosen by the
    caller, so neither is safe to log raw. The route template, such as
    ``/items/{item_id}``, has a bounded set of values and no personal data.

    Args:
        scope: ASGI scope of the request, as seen after routing.

    Returns:
        The matched route's path template, or ``UNMATCHED_ROUTE`` when no route
        matched (or routing has not happened yet).
    """
    return getattr(scope.get("route"), "path", UNMATCHED_ROUTE)


def request_id_of(request: Request) -> str | None:
    """Return the correlation id the logging middleware attached to the request.

    Args:
        request: The request being answered.

    Returns:
        The id, or None when the logging middleware did not run.
    """
    return getattr(request.state, "request_id", None)
