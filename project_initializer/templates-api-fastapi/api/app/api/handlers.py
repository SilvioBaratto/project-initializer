"""FastAPI exception handlers.

Renders the framework-free domain exceptions (``app/domain/exceptions.py``) into
standardized JSON HTTP responses and registers a handler for each type on the
app. This is the HTTP adapter for the domain error hierarchy.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BaseAPIException,
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    ExternalServiceError,
    RateLimitError,
    SecurityViolationError,
    ValidationError,
)

logger = logging.getLogger(__name__)


def create_error_response(
    status_code: int,
    message: str,
    error_code: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Create a standardized error response."""

    content: Dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }

    if details:
        content["error"]["details"] = details

    if request_id:
        content["error"]["request_id"] = request_id

    return JSONResponse(status_code=status_code, content=content)


def setup_exception_handlers(app: FastAPI) -> None:
    """Setup all exception handlers for the application."""

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        """Handle business logic validation errors"""

        logger.warning(
            f"Validation error: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "details": exc.details,
                "path": request.url.path,
                "method": request.method,
                "validation_error": True,  # Flag for validation monitoring
            },
        )

        return create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
            request_id=getattr(request.state, "request_id", None),
        )

    @app.exception_handler(SecurityViolationError)
    async def security_violation_handler(request: Request, exc: SecurityViolationError):
        """Handle security violation exceptions with enhanced logging"""

        # Log security events with high priority
        logger.error(
            f"SECURITY VIOLATION: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "details": exc.details,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "unknown"),
                "method": request.method,
                "security_event": True,  # Flag for security monitoring
            },
        )

        # Add security-specific headers
        response = create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
            request_id=getattr(request.state, "request_id", None),
        )

        # Add security headers
        response.headers["X-Security-Event"] = "violation_detected"
        response.headers["X-Request-Blocked"] = "true"

        return response

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(request: Request, exc: AuthenticationError):
        """Handle authentication errors with audit logging"""

        # Extract client information for audit trail
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        logger.warning(
            f"Authentication failed: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "method": request.method,
                "auth_failure": True,  # Flag for auth monitoring
            },
        )

        # Create response with auth-specific headers
        response = create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.error_code,
            details=getattr(exc, "details", {}),
            request_id=getattr(request.state, "request_id", None),
        )

        # Add authentication-specific headers
        response.headers["WWW-Authenticate"] = "Bearer"
        response.headers["X-Auth-Error"] = "true"

        return response

    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(request: Request, exc: AuthorizationError):
        """Handle authorization errors with permission tracking"""

        client_ip = request.client.host if request.client else "unknown"

        logger.warning(
            f"Authorization failed: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
                "client_ip": client_ip,
                "method": request.method,
                "authorization_failure": True,  # Flag for permission monitoring
            },
        )

        response = create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.error_code,
            details=getattr(exc, "details", {}),
            request_id=getattr(request.state, "request_id", None),
        )

        response.headers["X-Permission-Required"] = "true"

        return response

    @app.exception_handler(RateLimitError)
    async def rate_limit_handler(request: Request, exc: RateLimitError):
        """Handle rate limit exceptions with retry information"""

        logger.info(
            f"Rate limit exceeded: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
                "rate_limit_exceeded": True,
            },
        )

        response = create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
            request_id=getattr(request.state, "request_id", None),
        )

        # Add rate limiting headers
        retry_after = exc.details.get("retry_after", 60)
        response.headers["Retry-After"] = str(retry_after)
        response.headers["X-RateLimit-Exceeded"] = "true"

        return response

    @app.exception_handler(DatabaseTimeoutError)
    async def database_timeout_error_handler(
        request: Request, exc: DatabaseTimeoutError
    ):
        """Handle database timeout errors with specific monitoring"""

        logger.error(
            f"Database timeout error: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
                "timeout_duration": exc.details.get("timeout_duration"),
                "database_timeout_error": True,  # Flag for database monitoring
            },
        )

        response = create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
            request_id=getattr(request.state, "request_id", None),
        )

        response.headers["X-Database-Error"] = "timeout"
        response.headers["Retry-After"] = "5"  # Suggest retry after 5 seconds

        return response

    @app.exception_handler(DatabaseConnectionError)
    async def database_connection_error_handler(
        request: Request, exc: DatabaseConnectionError
    ):
        """Handle database connection errors with circuit breaker info"""

        logger.error(
            f"Database connection error: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
                "connection_info": exc.details.get("connection_info"),
                "database_connection_error": True,  # Flag for database monitoring
            },
        )

        response = create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
            request_id=getattr(request.state, "request_id", None),
        )

        response.headers["X-Database-Error"] = "connection_failed"
        response.headers["Retry-After"] = "10"  # Suggest retry after 10 seconds

        return response

    @app.exception_handler(ExternalServiceError)
    async def external_service_error_handler(
        request: Request, exc: ExternalServiceError
    ):
        """Handle external service errors with service monitoring"""

        logger.error(
            f"External service error: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
                "service": exc.details.get("service", "unknown"),
                "external_service_error": True,  # Flag for service monitoring
            },
        )

        response = create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
            request_id=getattr(request.state, "request_id", None),
        )

        response.headers["X-Service-Error"] = exc.details.get("service", "unknown")

        return response

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError):
        """Handle generic database errors"""

        logger.error(
            f"Database error: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
                "database_error": True,  # Flag for database monitoring
            },
        )

        return create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
            request_id=getattr(request.state, "request_id", None),
        )

    @app.exception_handler(BaseAPIException)
    async def api_exception_handler(request: Request, exc: BaseAPIException):
        """Handle custom API exceptions"""

        # Log the error
        logger.error(
            f"API Exception: {exc.error_code} - {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "details": exc.details,
                "path": request.url.path,
            },
        )

        return create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
            request_id=getattr(request.state, "request_id", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        """Handle Pydantic validation errors"""

        # Format validation errors
        errors = {}
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"][1:])
            if field not in errors:
                errors[field] = []
            errors[field].append(error["msg"])

        logger.warning(
            f"Validation error on {request.url.path}", extra={"errors": errors}
        )

        return create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Validation failed",
            error_code="VALIDATION_ERROR",
            details={"validation_errors": errors},
            request_id=getattr(request.state, "request_id", None),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle Starlette HTTP exceptions"""

        logger.warning(
            f"HTTP Exception: {exc.status_code} - {exc.detail}",
            extra={"path": request.url.path},
        )

        return create_error_response(
            status_code=exc.status_code,
            message=str(exc.detail),
            error_code=f"HTTP_{exc.status_code}",
            request_id=getattr(request.state, "request_id", None),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions"""

        logger.exception(f"Unexpected error on {request.url.path}", exc_info=exc)

        # Don't expose internal errors in production
        message = "An unexpected error occurred"
        if app.debug:
            message = str(exc)

        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=message,
            error_code="INTERNAL_SERVER_ERROR",
            request_id=getattr(request.state, "request_id", None),
        )
