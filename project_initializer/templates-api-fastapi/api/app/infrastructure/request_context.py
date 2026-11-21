"""Per-request correlation id shared between the middleware and the log formatter.

A context variable follows the request across ``await`` points and into the
worker thread that runs a sync endpoint, so any log line emitted while a request
is handled can carry the request id without passing it through every call.
"""

from contextvars import ContextVar, Token

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def bind_request_id(request_id: str) -> Token[str | None]:
    """Make ``request_id`` the current request's correlation id.

    Args:
        request_id: Identifier to attach to every log line of this request.

    Returns:
        A token to hand back to ``reset_request_id`` when the request ends.
    """
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the correlation id that was current before ``bind_request_id``.

    Args:
        token: The value returned by the matching ``bind_request_id`` call.
    """
    _request_id.reset(token)


def current_request_id() -> str | None:
    """Return the correlation id of the request being handled, or None outside one."""
    return _request_id.get()
