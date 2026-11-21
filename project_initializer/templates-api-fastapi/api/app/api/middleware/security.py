"""Security response headers.

The header sets are computed once at construction, not per request, and the
documentation pages get their own content security policy only when they are
served at all.
"""

from collections.abc import Mapping
from types import MappingProxyType

from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.docs import DOCS_CONTENT_SECURITY_POLICY, DOCS_PAGE_PATHS
from app.api.middleware.response_headers import with_response_headers

HSTS_MAX_AGE_SECONDS = 31_536_000
CONTENT_SECURITY_POLICY_HEADER = "Content-Security-Policy"
# A JSON API renders nothing, so it may load nothing.
API_CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'"

_DISABLED_BROWSER_FEATURES = (
    "geolocation",
    "microphone",
    "camera",
    "payment",
    "usb",
    "magnetometer",
    "gyroscope",
    "fullscreen",
)

BASE_SECURITY_HEADERS: Mapping[str, str] = MappingProxyType(
    {
        # The legacy browser XSS auditor is itself an attack vector; the policy that
        # protects a modern browser is the Content-Security-Policy below.
        "X-XSS-Protection": "0",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Strict-Transport-Security": (
            f"max-age={HSTS_MAX_AGE_SECONDS}; includeSubDomains"
        ),
        "Permissions-Policy": ", ".join(
            f"{feature}=()" for feature in _DISABLED_BROWSER_FEATURES
        ),
    }
)


class SecurityHeadersMiddleware:
    """Adds the security headers to every HTTP response.

    The headers never announce the application version, so a scanner cannot
    match it against known vulnerabilities.
    """

    def __init__(self, app: ASGIApp, *, docs_enabled: bool) -> None:
        """Prepare the header sets.

        Args:
            app: The next application in the middleware chain.
            docs_enabled: Whether the documentation pages are served. When true
                they get a policy that lets them load the pinned CDN assets; the
                relaxed policy never applies to any other path.
        """
        self.app = app
        self._api_headers = {
            **BASE_SECURITY_HEADERS,
            CONTENT_SECURITY_POLICY_HEADER: API_CONTENT_SECURITY_POLICY,
        }
        self._docs_headers = {
            **BASE_SECURITY_HEADERS,
            CONTENT_SECURITY_POLICY_HEADER: DOCS_CONTENT_SECURITY_POLICY,
        }
        self._docs_pages = DOCS_PAGE_PATHS if docs_enabled else frozenset()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI connection; headers are added to HTTP responses."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = (
            self._docs_headers
            if scope["path"] in self._docs_pages
            else self._api_headers
        )

        await self.app(scope, receive, with_response_headers(send, headers))
