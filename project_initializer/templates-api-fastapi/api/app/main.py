"""FastAPI application factory for FastAPI Template"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

from app.config import settings
from app.database import database_manager, init_db, close_db
from app.exceptions import setup_exception_handlers
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limiting import RateLimitingMiddleware
from app.api.v1.router import api_router

# Load environment variables FIRST, before any other imports
# This ensures libraries can access env vars
load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format=(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if settings.log_format == "text"
        else '{"timestamp": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
    ),
)
logger = logging.getLogger(__name__)


# OpenAPI metadata — per-tag descriptions render as grouped sections in Swagger /
# ReDoc. Order here is the order tags appear in the docs. Edit the descriptions
# (and the contact / license below) to match your project before shipping.
TAGS_METADATA = [
    {
        "name": "Items",
        "description": "CRUD for the example **Item** resource — the reference DB-backed router.",
    },
    {
        "name": "Users",
        "description": "The authenticated user's own profile (`/users/me`).",
    },
    {
        "name": "Auth",
        "description": "Authentication — token validation and (token variant) JWT register/login.",
    },
    {
        "name": "Chatbot",
        "description": "BAML-powered LLM chat: complete and streaming responses.",
    },
    {
        "name": "Test",
        "description": "Demo / health-style routes used to exercise the stack.",
    },
]

# Project identity constants — set once at scaffold time, not per-deployment, so
# they live here rather than in Settings (env vars). Replace with your own.
CONTACT_INFO = {"name": "API Support", "email": "support@example.com"}
LICENSE_INFO = {"name": "MIT", "identifier": "MIT"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.project_name}...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    try:
        # Initialize database
        init_db()
        logger.info("Database initialized successfully")

        # Test database connection
        try:
            health_check_passed = database_manager.health_check()
            if health_check_passed:
                logger.info("Database health check passed")
            else:
                logger.warning("Database health check failed but continuing startup")
        except Exception as e:
            logger.warning(f"Database health check failed but continuing startup: {e}")

        logger.info(f"{settings.project_name} startup complete")
        yield

    except Exception as e:
        logger.error(f"Startup error: {e}")
        if settings.is_development:
            logger.warning("Continuing startup in development mode despite errors")
            yield
        else:
            raise

    # Shutdown
    logger.info(f"Shutting down {settings.project_name}...")

    try:
        close_db()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application"""

    # Create FastAPI application with correct OpenAPI configuration
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        summary="Modern API scaffold with layered architecture and BAML LLM integration.",
        description="Modern API",
        openapi_tags=TAGS_METADATA,
        contact=CONTACT_INFO,
        license_info=LICENSE_INFO,
        docs_url=None,  # Disable default docs - we'll set up custom ones
        redoc_url=None,  # Disable default redoc - we'll set up custom ones
        openapi_url=(
            "/openapi.json" if (settings.debug or settings.is_staging) else None
        ),  # Keep OpenAPI JSON accessible
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Setup exception handlers
    setup_exception_handlers(app)

    # Add middleware stack (order matters - reverse order of execution)

    # 1. CORS middleware (outermost)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "User-Agent",
            "X-Requested-With",
            "X-Client-Info",
            "X-Dev-User",
        ],
        expose_headers=["X-Total-Count", "X-Rate-Limit-Remaining"],
        max_age=3600,  # Cache preflight requests for 1 hour
    )

    # 2. Rate limiting middleware (enabled in production and staging)
    if settings.is_production_like:
        app.add_middleware(
            RateLimitingMiddleware,
            requests=settings.rate_limit_requests,
            window=settings.rate_limit_window,
        )

    # 3. Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 4. Request logging middleware (innermost)
    if settings.debug or settings.log_level.upper() in ["DEBUG", "INFO"]:
        app.add_middleware(LoggingMiddleware)

    # Add API routes
    app.include_router(api_router, prefix=settings.api_v1_str)

    # Add health check endpoints
    setup_health_endpoints(app)

    # Setup documentation endpoints based on environment
    setup_documentation_endpoints(app)

    return app


def setup_health_endpoints(app: FastAPI) -> None:
    """Setup health check and monitoring endpoints"""

    @app.get("/")
    async def read_root() -> Dict[str, Any]:
        """Root endpoint with API information"""
        return {
            "message": f"Welcome to the {settings.project_name}!",
            "version": settings.version,
            "status": "operational",
            "environment": settings.environment,
            "api_version": "v1",
            "docs_url": "/docs" if settings.debug else None,
            "redoc_url": "/redoc" if settings.debug else None,
        }

    @app.get("/health")
    async def health_check() -> Dict[str, str]:
        """Simple health check endpoint - just return OK"""
        return {"status": "ok"}


def setup_documentation_endpoints(app: FastAPI) -> None:
    """Setup documentation endpoints - always accessible in local development"""

    logger.info("Setting up open documentation endpoints for local development")

    @app.get("/docs", include_in_schema=False)
    def swagger_ui():
        """Swagger UI - open access for local development"""
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{app.title} – API Documentation",
            swagger_js_url="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js",
            swagger_css_url="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    def redoc_ui():
        """ReDoc UI - open access for local development"""
        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{app.title} – API Documentation",
            redoc_js_url="https://unpkg.com/redoc@2.1.0/bundles/redoc.standalone.js",
        )

    @app.get("/openapi.json", include_in_schema=False)
    def get_openapi_json():
        """OpenAPI JSON schema.

        Delegate to ``app.openapi()`` so the served schema reflects ALL metadata
        set on the app (summary/description/openapi_tags/contact/license_info).
        The 3-arg ``get_openapi(title, version, routes)`` form silently dropped
        them. This route is the sole responder only when ``openapi_url`` is None
        (production); otherwise FastAPI's built-in route serves the same schema.
        """
        return app.openapi()


# Create the application instance
app = create_application()

# For development server compatibility
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
