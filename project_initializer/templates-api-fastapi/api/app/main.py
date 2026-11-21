"""FastAPI application factory."""
# ruff: noqa: E402
# load_configuration() must run before any import that instantiates Settings,
# because Settings reads os.environ once at import time. The imports below it
# therefore sit after a statement on purpose.

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.infrastructure.config import load_configuration

load_configuration()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.api.docs import OPENAPI_PATH, register_docs_routes
from app.api.handlers import setup_exception_handlers
from app.api.headers import (
    LIMIT_HEADER,
    REMAINING_HEADER,
    REQUEST_ID_HEADER,
    RESET_HEADER,
    RETRY_AFTER_HEADER,
)
from app.api.health import router as health_router
from app.api.middleware.logging import RequestLoggingMiddleware
from app.api.middleware.rate_limiting import RateLimitingMiddleware
from app.api.middleware.security import SecurityHeadersMiddleware
from app.api.middleware.unhandled_errors import UnhandledErrorMiddleware
from app.api.v1.router import api_router
from app.infrastructure.database import (
    close_db,
    database_manager,
    init_db,
    run_shutdown_hooks,
)
from app.infrastructure.health import probe_database
from app.infrastructure.log_level import reload_log_level_on_sighup
from app.infrastructure.settings import Settings, settings
from app.infrastructure.structured_logging import configure_logging

logger = logging.getLogger(__name__)

CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
# X-User-Id is the development-only identity header honoured by the base
# variant's auth dependency; browser tools used during development may send it.
CORS_ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "Accept",
    "Origin",
    "User-Agent",
    "X-Requested-With",
    "X-Client-Info",
    REQUEST_ID_HEADER,
    "X-User-Id",
]
# Without this list a browser hides every header outside the CORS-safelisted
# set, so a client could not read the request id or when to retry.
CORS_EXPOSED_HEADERS = [
    REQUEST_ID_HEADER,
    RETRY_AFTER_HEADER,
    LIMIT_HEADER,
    REMAINING_HEADER,
    RESET_HEADER,
]
CORS_PREFLIGHT_MAX_AGE_SECONDS = 600

API_SUMMARY = "Layered API scaffold."
# Identity metadata is fixed when the project is scaffolded, not per deployment,
# so it lives here instead of in Settings. Replace it with your own.
CONTACT_INFO = {"name": "API Support", "email": "support@example.com"}
LICENSE_INFO = {"name": "MIT", "identifier": "MIT"}

# The order here is the order of the sections in the generated docs.
TAGS_METADATA = [
    {
        "name": "Items",
        "description": "CRUD for the example **Item** resource, the reference "
        "database-backed router.",
    },
    {
        "name": "Auth",
        "description": "Who the caller is, plus token validation and JWT "
        "register and login in the token variant.",
    },
    {
        "name": "Test",
        "description": "Demo routes used to exercise the stack.",
    },
    {
        "name": "Health",
        "description": "Liveness and readiness probes for orchestrators.",
    },
]

DEV_SERVER_HOST = "127.0.0.1"
DEV_SERVER_PORT = 8000


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepare the database engine on startup and release it on shutdown.

    Shutdown first runs the hooks that optional components registered, such as
    the async overlay's engine disposal, on the event loop that owns their
    resources, then disposes the synchronous engine.

    A database outage at startup is logged and never aborts the process: the
    readiness probe reports it, so the orchestrator keeps traffic away until the
    database is back, while the liveness probe keeps the process alive.

    While the application serves requests, SIGHUP makes the process re-read
    ``LOG_LEVEL`` (see ``app.infrastructure.log_level``), so an operator can
    change the verbosity without a restart.

    Args:
        app: The application being started.

    Yields:
        Once, while the application serves requests.
    """
    logger.info("app.startup", extra={"app_name": app.title})
    init_db()
    health = await run_in_threadpool(probe_database, database_manager)
    if not health.is_up:
        logger.warning(
            "app.startup_database_unavailable", extra={"circuit": health.circuit}
        )
    try:
        with reload_log_level_on_sighup():
            yield
    finally:
        await run_shutdown_hooks()
        close_db()
        logger.info("app.shutdown", extra={"app_name": app.title})


def _add_middleware(app: FastAPI, app_settings: Settings) -> None:
    # Starlette inserts each added middleware at the front, so the last one added
    # is the outermost. CORS must be outermost: its headers then also appear on
    # 429 responses, and preflight requests never consume rate-limit quota. The
    # catch-all sits inside the logging, security and CORS layers so the 500 it
    # sends carries their headers, and outside the limiter so a failure there is
    # answered too.
    if app_settings.is_production_like:
        app.add_middleware(
            RateLimitingMiddleware,
            requests=app_settings.rate_limit_requests,
            window_seconds=app_settings.rate_limit_window,
        )
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(
        SecurityHeadersMiddleware, docs_enabled=app_settings.docs_enabled
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins_list,
        # The API authenticates with a bearer header, never with cookies, so no
        # credentialed cross-origin request is needed.
        allow_credentials=False,
        allow_methods=CORS_ALLOWED_METHODS,
        allow_headers=CORS_ALLOWED_HEADERS,
        expose_headers=CORS_EXPOSED_HEADERS,
        max_age=CORS_PREFLIGHT_MAX_AGE_SECONDS,
    )


def create_application(app_settings: Settings = settings) -> FastAPI:
    """Build and configure the FastAPI application.

    Args:
        app_settings: Configuration to build from; tests pass their own.

    Returns:
        The application with logging, middleware, error handlers and routes in
        place. The interactive docs and the OpenAPI schema are served only when
        ``app_settings.docs_enabled`` is true.
    """
    configure_logging(app_settings.log_level, app_settings.log_format)
    app = FastAPI(
        title=app_settings.project_name,
        version=app_settings.version,
        summary=API_SUMMARY,
        openapi_tags=TAGS_METADATA,
        contact=CONTACT_INFO,
        license_info=LICENSE_INFO,
        docs_url=None,
        redoc_url=None,
        openapi_url=OPENAPI_PATH if app_settings.docs_enabled else None,
        debug=app_settings.debug,
        lifespan=lifespan,
    )
    setup_exception_handlers(app)
    _add_middleware(app, app_settings)
    app.include_router(health_router)
    app.include_router(api_router, prefix=app_settings.api_v1_str)
    if app_settings.docs_enabled:
        register_docs_routes(app)
    return app


app = create_application()


def run_development_server() -> None:
    """Serve the application with uvicorn for local development.

    The access log is switched off because the structured ``http.request`` record
    replaces it, and uvicorn's line prints the client address and the raw query
    string.
    """
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=DEV_SERVER_HOST,
        port=DEV_SERVER_PORT,
        reload=settings.debug,
        log_level=settings.log_level,
        access_log=False,
    )


if __name__ == "__main__":
    run_development_server()
