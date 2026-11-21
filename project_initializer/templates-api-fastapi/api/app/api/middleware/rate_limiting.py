"""Per-client request rate limiting.

State is a sliding window of request times held in this process's memory, so the
limit applies per worker process, not across replicas; put a gateway or a shared
store such as Redis in front when the service scales out. The client is identified
by the peer address of the connection. Behind a reverse proxy that address is the
proxy's, so every caller would share one bucket unless uvicorn is told which
proxies to trust (``--forwarded-allow-ips`` or ``FORWARDED_ALLOW_IPS``), after
which it rewrites the peer address from ``X-Forwarded-For``.
"""

import ipaddress
import math
import time
from collections import deque
from collections.abc import Callable

from fastapi import status
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.errors import error_response
from app.api.headers import (
    LIMIT_HEADER,
    REMAINING_HEADER,
    RESET_HEADER,
    RETRY_AFTER_HEADER,
)
from app.api.health import HEALTH_PATHS
from app.api.middleware.response_headers import with_response_headers
from app.infrastructure.request_context import current_request_id

RATE_LIMITED_CODE = "RATE_LIMITED"
RATE_LIMITED_MESSAGE = "Too many requests"
UNKNOWN_CLIENT = "unknown"
# One subscriber normally holds a whole /64, so keying on the full address would
# let a single client rotate through 2**64 addresses to dodge the limit.
IPV6_PREFIX_LENGTH = 64
MAX_TRACKED_CLIENTS = 100_000


class RateLimitingMiddleware:
    """Rejects a client that sends more than ``requests`` in ``window_seconds``.

    Allowed responses carry ``X-RateLimit-Limit``, ``X-RateLimit-Remaining`` and
    ``X-RateLimit-Reset`` (seconds until the oldest counted request leaves the
    window). A rejected request gets 429 with the error envelope and
    ``Retry-After``.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        requests: int,
        window_seconds: int,
        exempt_paths: frozenset[str] = HEALTH_PATHS,
        max_tracked_clients: int = MAX_TRACKED_CLIENTS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Configure the limiter.

        Args:
            app: The next application in the middleware chain.
            requests: Requests one client may send within the window.
            window_seconds: Length of the sliding window.
            exempt_paths: Paths that are never counted or limited.
            max_tracked_clients: Upper bound on the clients whose window is
                remembered. When it is reached, the client tracked longest ago is
                forgotten, which bounds memory under an address scan at the cost
                of resetting that one client's quota.
            clock: Monotonic time source in seconds; tests inject a fake.
        """
        self.app = app
        self._requests = requests
        self._window_seconds = window_seconds
        self._exempt_paths = exempt_paths
        self._max_tracked_clients = max_tracked_clients
        self._clock = clock
        self._arrivals: dict[str, deque[float]] = {}
        self._last_sweep = clock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI connection; only non-exempt HTTP requests are limited."""
        if scope["type"] != "http" or scope["path"] in self._exempt_paths:
            await self.app(scope, receive, send)
            return

        now = self._clock()
        self._sweep_if_due(now)
        arrivals = self._arrivals_of(_client_key(scope))
        self._discard_expired(arrivals, now)

        if len(arrivals) >= self._requests:
            await self._reject(scope, receive, send, arrivals, now)
            return

        arrivals.append(now)
        limit_headers = self._limit_headers(
            remaining=self._requests - len(arrivals),
            reset_seconds=self._seconds_until_reset(arrivals, now),
        )
        await self.app(scope, receive, with_response_headers(send, limit_headers))

    async def _reject(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        arrivals: deque[float],
        now: float,
    ) -> None:
        reset_seconds = self._seconds_until_reset(arrivals, now)
        response = error_response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            RATE_LIMITED_CODE,
            RATE_LIMITED_MESSAGE,
            request_id=current_request_id(),
            headers={
                RETRY_AFTER_HEADER: str(reset_seconds),
                **self._limit_headers(remaining=0, reset_seconds=reset_seconds),
            },
        )
        await response(scope, receive, send)

    def _limit_headers(self, *, remaining: int, reset_seconds: int) -> dict[str, str]:
        return {
            LIMIT_HEADER: str(self._requests),
            REMAINING_HEADER: str(remaining),
            RESET_HEADER: str(reset_seconds),
        }

    def _arrivals_of(self, client_key: str) -> deque[float]:
        known = self._arrivals.get(client_key)
        if known is not None:
            return known
        if len(self._arrivals) >= self._max_tracked_clients:
            del self._arrivals[next(iter(self._arrivals))]
        return self._arrivals.setdefault(client_key, deque())

    def _discard_expired(self, arrivals: deque[float], now: float) -> None:
        while arrivals and arrivals[0] <= now - self._window_seconds:
            arrivals.popleft()

    def _seconds_until_reset(self, arrivals: deque[float], now: float) -> int:
        oldest = arrivals[0]
        return max(1, math.ceil(oldest + self._window_seconds - now))

    def _sweep_if_due(self, now: float) -> None:
        # Without a sweep every address ever seen would keep an entry forever,
        # which a scan over many addresses turns into unbounded memory growth.
        if now - self._last_sweep < self._window_seconds:
            return
        self._last_sweep = now
        cutoff = now - self._window_seconds
        stale = [
            key
            for key, arrivals in self._arrivals.items()
            if not arrivals or arrivals[-1] <= cutoff
        ]
        for key in stale:
            del self._arrivals[key]


def _client_key(scope: Scope) -> str:
    client = scope.get("client")
    if not client:
        return UNKNOWN_CLIENT
    return _bucket_of(client[0])


def _bucket_of(host: str) -> str:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        network = ipaddress.IPv6Network((address, IPV6_PREFIX_LENGTH), strict=False)
        return str(network)
    return str(address)
