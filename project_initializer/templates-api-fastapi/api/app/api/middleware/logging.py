"""Request correlation id and one access-log line per request.

The middleware is pure ASGI rather than ``BaseHTTPMiddleware``: the latter runs the
application in a separate task, which breaks context variables and streaming
responses. It deliberately logs no request or response bodies, no query string
and no client address, because those carry tokens, emails and other personal data.
The path is logged as the matched route template, never as the raw URL path, since
a path parameter can hold user text.
"""

import logging
import re
import time
import uuid
from http import HTTPStatus

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import route_template
from app.api.headers import REQUEST_ID_HEADER
from app.infrastructure.request_context import bind_request_id, reset_request_id

REQUEST_ID_PATTERN = r"^[A-Za-z0-9._-]{1,64}$"
REQUEST_LOG_MESSAGE = "http.request"
MILLISECONDS_PER_SECOND = 1000

# An incoming id is reused so a caller (or a gateway) can correlate its own logs
# with ours; the pattern keeps hostile values out of the log pipeline.
_REQUEST_ID_RE = re.compile(REQUEST_ID_PATTERN)

logger = logging.getLogger(__name__)


def _resolve_request_id(scope: Scope) -> str:
    incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
    if incoming and _REQUEST_ID_RE.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


def _log_request(scope: Scope, status_code: int, started: float) -> None:
    logger.info(
        REQUEST_LOG_MESSAGE,
        extra={
            "method": scope["method"],
            "path": route_template(scope),
            "status": status_code,
            "duration_ms": round(
                (time.perf_counter() - started) * MILLISECONDS_PER_SECOND, 2
            ),
        },
    )


class _ResponseTracker:
    """Send wrapper that stamps the request id on the response and notes its status."""

    def __init__(self, send: Send, request_id: str) -> None:
        self._send = send
        self._request_id = request_id
        # An exception that escapes the application is answered with a 500 by an
        # outer layer, so 500 is the right value when no response start is seen.
        self.status_code = HTTPStatus.INTERNAL_SERVER_ERROR.value

    async def __call__(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.status_code = message["status"]
            message.setdefault("headers", [])
            MutableHeaders(scope=message)[REQUEST_ID_HEADER] = self._request_id
        await self._send(message)


class RequestLoggingMiddleware:
    """Assigns every HTTP request an id and logs one ``http.request`` line.

    The id is bound to a context variable (so every log line of the request
    carries it), stored in ``scope["state"]["request_id"]`` (so error handlers
    can put it in the response body) and returned in the ``X-Request-ID``
    response header.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap an ASGI application.

        Args:
            app: The next application in the middleware chain.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI connection; only HTTP requests are logged."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        token = bind_request_id(request_id)
        tracker = _ResponseTracker(send, request_id)
        started = time.perf_counter()
        try:
            await self.app(scope, receive, tracker)
        finally:
            _log_request(scope, tracker.status_code, started)
            reset_request_id(token)
