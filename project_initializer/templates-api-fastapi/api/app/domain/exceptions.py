"""Domain exception types.

Pure exception hierarchy with no framework imports — the FastAPI exception
handlers that render these into HTTP responses live in ``app/api/handlers.py``.
Status codes use the stdlib :class:`http.HTTPStatus` (an ``IntEnum``) so this
module stays framework-free while the codes remain plain integers for the
handler layer.
"""

from http import HTTPStatus
from typing import Any, Dict, List, Optional


class BaseAPIException(Exception):
    """Base exception class for API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(BaseAPIException):
    """Raised when business logic validation fails."""

    def __init__(self, message: str, errors: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            details={"errors": errors or {}},
        )


class AuthenticationError(BaseAPIException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            status_code=HTTPStatus.UNAUTHORIZED,
            error_code="AUTHENTICATION_ERROR",
        )


class AuthorizationError(BaseAPIException):
    """Raised when user lacks permission."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            status_code=HTTPStatus.FORBIDDEN,
            error_code="AUTHORIZATION_ERROR",
        )


class NotFoundError(BaseAPIException):
    """Raised when a resource is not found."""

    def __init__(self, resource: str, identifier: Optional[Any] = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(
            message=message,
            status_code=HTTPStatus.NOT_FOUND,
            error_code="NOT_FOUND",
        )


class ConflictError(BaseAPIException):
    """Raised when there's a conflict with existing data."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=HTTPStatus.CONFLICT,
            error_code="CONFLICT_ERROR",
        )


class RateLimitError(BaseAPIException):
    """Raised when rate limit is exceeded."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None
    ):
        super().__init__(
            message=message,
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_ERROR",
            details={"retry_after": retry_after} if retry_after else {},
        )


class ExternalServiceError(BaseAPIException):
    """Raised when an external service fails."""

    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service}: {message}",
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service": service},
        )


class DatabaseError(BaseAPIException):
    """Raised when database operations fail."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(
            message=message,
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR",
        )


class DatabaseTimeoutError(DatabaseError):
    """Raised when database operations timeout."""

    def __init__(
        self,
        message: str = "Database operation timed out",
        timeout_duration: Optional[float] = None,
    ):
        super().__init__(message)
        self.error_code = "DATABASE_TIMEOUT_ERROR"
        if timeout_duration:
            self.details = {"timeout_duration": timeout_duration}


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(
        self,
        message: str = "Database connection failed",
        connection_info: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.error_code = "DATABASE_CONNECTION_ERROR"
        if connection_info:
            self.details = {"connection_info": connection_info}


class TokenValidationError(AuthenticationError):
    """Raised when JWT token validation fails."""

    def __init__(
        self,
        message: str = "Token validation failed",
        token_info: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.details = {"token_info": token_info or {}}


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired."""

    def __init__(
        self, message: str = "Token has expired", expired_at: Optional[str] = None
    ):
        super().__init__(message)
        if expired_at:
            self.details = {"expired_at": expired_at}


class InvalidTokenFormatError(AuthenticationError):
    """Raised when token format is invalid."""

    def __init__(self, message: str = "Invalid token format"):
        super().__init__(message)
        self.details = {"expected_format": "Bearer <JWT_TOKEN>"}


class UserInactiveError(AuthenticationError):
    """Raised when user account is inactive."""

    def __init__(self, user_id: Optional[str] = None):
        message = "User account is inactive or disabled"
        super().__init__(message)
        if user_id:
            self.details = {"user_id": user_id}


class InsufficientPermissionsError(AuthorizationError):
    """Raised when user lacks specific permissions."""

    def __init__(
        self,
        required_permissions: List[str],
        user_permissions: Optional[List[str]] = None,
    ):
        message = (
            f"Insufficient permissions. Required: {', '.join(required_permissions)}"
        )
        super().__init__(message)
        self.details = {
            "required_permissions": required_permissions,
            "user_permissions": user_permissions or [],
        }


class SecurityViolationError(BaseAPIException):
    """Raised when security policy is violated."""

    def __init__(self, violation_type: str, details: Optional[Dict[str, Any]] = None):
        message = f"Security policy violation: {violation_type}"
        super().__init__(
            message=message,
            status_code=HTTPStatus.FORBIDDEN,
            error_code="SECURITY_VIOLATION",
            details=details or {},
        )


class SuspiciousActivityError(SecurityViolationError):
    """Raised when suspicious activity is detected."""

    def __init__(self, activity_type: str, client_ip: Optional[str] = None):
        details = {}
        if client_ip:
            details["client_ip"] = client_ip
        super().__init__(activity_type, details)


class AuthServiceUnavailableError(ExternalServiceError):
    """Raised when authentication service is unavailable."""

    def __init__(self, service_name: str = "Authentication Service"):
        super().__init__(service_name, "Service temporarily unavailable")


class CacheError(BaseAPIException):
    """Raised when cache operations fail."""

    def __init__(self, operation: str, message: Optional[str] = None):
        error_message = f"Cache {operation} failed"
        if message:
            error_message += f": {message}"

        super().__init__(
            message=error_message,
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            error_code="CACHE_ERROR",
            details={"operation": operation},
        )
