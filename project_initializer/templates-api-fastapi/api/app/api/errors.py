"""Builders for the error envelope, shared by handlers, middleware and routes."""

from collections.abc import Mapping
from datetime import UTC, datetime
from http import HTTPStatus
from types import MappingProxyType
from typing import Any
from weakref import WeakKeyDictionary

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute, iter_route_contexts
from starlette.applications import Starlette
from starlette.routing import BaseRoute, Mount
from starlette.types import Scope

from app.api.schemas.errors import ErrorBody, ErrorEnvelope, FieldError

UNMATCHED_ROUTE = "unmatched"

# FastAPI puts a route declared on the application or a router in ``scope["route"]``,
# and that object has lost the prefix given to ``include_router``. For a plain
# Starlette route or a mount it sets no route at all and leaves only the handler in
# ``scope["endpoint"]``. Only ``iter_route_contexts`` exposes the whole template,
# and it walks every router on each call, so each application keeps a lookup from
# the identity of what the scope holds to the template. Routes may be added after
# the first request, so an identity missing from the lookup rebuilds it.
_TEMPLATES_BY_APP: WeakKeyDictionary[Starlette, dict[int, str]] = WeakKeyDictionary()

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


def _left_in_scope(route: BaseRoute) -> object | None:
    """The object routing leaves in the scope when ``route`` serves a request."""
    if isinstance(route, APIRoute):
        return route
    if isinstance(route, Mount):
        return route.app
    return getattr(route, "endpoint", None)


def _templates_of(app: Starlette) -> dict[int, str]:
    templates: dict[int, str] = {}
    for context in iter_route_contexts(app.routes):
        in_scope = _left_in_scope(context.original_route)
        if in_scope is not None and context.path is not None:
            templates[id(in_scope)] = context.path
    return templates


def route_template(scope: Scope) -> str:
    """Name the route that served a request, for logs.

    A path parameter can hold user text and an unmatched path is chosen by the
    caller, so neither is safe to log raw. The route template, such as
    ``/api/v1/items/{item_id}``, has a bounded set of values and no personal data.

    The template includes the prefix given to ``include_router``. A plain Starlette
    route, such as ``/openapi.json``, is named by its path and a mounted application
    by its mount path. A router, route or endpoint registered at several paths is
    one object, so the registrations cannot be told apart and the template of the
    later one is logged for all of them.

    Args:
        scope: ASGI scope of the request, as seen after routing.

    Returns:
        The path template of the route, plain route or mount that served the
        request, or ``UNMATCHED_ROUTE`` when none did (or routing has not happened
        yet) or when the application does not list the plain route or mount. Without
        an application in the scope, or for a declared route it does not list, the
        route's own unprefixed path.
    """
    route = scope.get("route")
    in_scope = route if route is not None else scope.get("endpoint")
    if in_scope is None:
        return UNMATCHED_ROUTE
    declared_path = getattr(route, "path", UNMATCHED_ROUTE)
    app = scope.get("app")
    if app is None:
        return declared_path
    templates = _TEMPLATES_BY_APP.get(app)
    if templates is None or id(in_scope) not in templates:
        templates = _TEMPLATES_BY_APP[app] = _templates_of(app)
    return templates.get(id(in_scope), declared_path)


def request_id_of(request: Request) -> str | None:
    """Return the correlation id the logging middleware attached to the request.

    Args:
        request: The request being answered.

    Returns:
        The id, or None when the logging middleware did not run.
    """
    return getattr(request.state, "request_id", None)
