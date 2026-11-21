"""Catch-all for exceptions that no route or handler answered.

Starlette's own server-error layer sits outside every middleware and re-raises
after it has answered, so without this middleware each crash is logged twice (the
second time by the ASGI server, without a request id) and its 500 response misses
the request id, security and CORS headers that the layers around it add. This
middleware sits inside those layers, so the 500 it sends passes through all of
them, and it never re-raises, so the failure is logged exactly once.
"""

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.handlers import log_unexpected_error, unexpected_error_response


class UnhandledErrorMiddleware:
    """Answers an unexpected exception with the generic 500 error envelope.

    Only ``Exception`` is caught: cancellation and shutdown signals derive from
    ``BaseException`` and must keep propagating.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap an ASGI application.

        Args:
            app: The next application in the middleware chain.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI connection; only HTTP requests are guarded."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_noting_start(message: Message) -> None:
            """Forward the message and remember that the status line went out."""
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_noting_start)
        except Exception as error:
            request = Request(scope)
            log_unexpected_error(request, error)
            # Once the status line is out a different one cannot follow; the
            # server then ends the connection, which tells the client the
            # response is incomplete.
            if not response_started:
                await unexpected_error_response(request)(scope, receive, send)
