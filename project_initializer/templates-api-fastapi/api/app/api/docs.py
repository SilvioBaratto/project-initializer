"""Interactive API documentation (Swagger UI and ReDoc).

The pages load their scripts from a CDN at pinned versions, which the
documentation content security policy allows. They are registered only when
``Settings.docs_enabled`` is true; otherwise the OpenAPI schema is not served
either, so a production deployment does not publish its own route map.
"""

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse

OPENAPI_PATH = "/openapi.json"
SWAGGER_PATH = "/docs"
REDOC_PATH = "/redoc"
# The schema is JSON that no browser renders, so it keeps the strict policy; only
# the two HTML pages need the CDN-friendly one.
DOCS_PAGE_PATHS = frozenset({SWAGGER_PATH, REDOC_PATH})
DOCS_PATHS = DOCS_PAGE_PATHS | {OPENAPI_PATH}

# Pinned to exact versions: a floating tag would let a CDN-side release change
# the script that runs on the documentation page.
CDN_ORIGIN = "https://cdn.jsdelivr.net"
CDN_BASE_URL = f"{CDN_ORIGIN}/npm"
SWAGGER_UI_JS_URL = f"{CDN_BASE_URL}/swagger-ui-dist@5.35.1/swagger-ui-bundle.js"
SWAGGER_UI_CSS_URL = f"{CDN_BASE_URL}/swagger-ui-dist@5.35.1/swagger-ui.css"
REDOC_JS_URL = f"{CDN_BASE_URL}/redoc@2.5.4/bundles/redoc.standalone.js"

# Both pages ship inline bootstrap code, hence 'unsafe-inline' for scripts and
# styles; ReDoc renders its search index in a blob worker. Everything else stays
# locked down, and the pages cannot be framed.
DOCS_CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        f"script-src 'self' 'unsafe-inline' {CDN_ORIGIN}",
        f"style-src 'self' 'unsafe-inline' {CDN_ORIGIN}",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "worker-src blob:",
        "frame-ancestors 'none'",
    )
)

# An empty data URL stops the browser from fetching a third-party favicon.
BLANK_FAVICON_URL = "data:,"


def register_docs_routes(app: FastAPI) -> None:
    """Add the Swagger UI and ReDoc pages to the application.

    Call it only when the application serves its OpenAPI schema
    (``app.openapi_url`` is set); the pages load the schema from there.

    Args:
        app: The application to add the routes to.
    """

    @app.get(SWAGGER_PATH, include_in_schema=False)
    def swagger_ui() -> HTMLResponse:
        """Serve the Swagger UI page."""
        return get_swagger_ui_html(
            openapi_url=OPENAPI_PATH,
            title=f"{app.title} - API documentation",
            swagger_js_url=SWAGGER_UI_JS_URL,
            swagger_css_url=SWAGGER_UI_CSS_URL,
            swagger_favicon_url=BLANK_FAVICON_URL,
        )

    @app.get(REDOC_PATH, include_in_schema=False)
    def redoc_ui() -> HTMLResponse:
        """Serve the ReDoc page."""
        return get_redoc_html(
            openapi_url=OPENAPI_PATH,
            title=f"{app.title} - API documentation",
            redoc_js_url=REDOC_JS_URL,
            redoc_favicon_url=BLANK_FAVICON_URL,
            with_google_fonts=False,
        )
