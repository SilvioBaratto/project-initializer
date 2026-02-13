"""Global dependencies for the application — token-based authentication"""

import secrets
import time
import logging
from typing import Optional, Annotated, Any

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

# Warn on insecure token at import time
if settings.auth_token == "changeme" or len(settings.auth_token) < 16:
    logger.warning(
        "AUTH_TOKEN is insecure (default or too short). "
        "Set a strong AUTH_TOKEN (>= 16 chars) before deploying."
    )

# Bearer token scheme
_bearer_scheme = HTTPBearer(auto_error=False)


def _validate_token(credentials: Optional[HTTPAuthorizationCredentials]) -> None:
    """Validate Bearer token against configured AUTH_TOKEN."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not secrets.compare_digest(credentials.credentials, settings.auth_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ===========================
# User Authentication
# ===========================


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """
    Validate Bearer token and return a user context dict.

    Returns a minimal user dict. Extend this to look up a real user
    from the database if needed.
    """
    _validate_token(credentials)
    return {
        "id": "token-user",
        "email": "token-user@app.local",
        "username": "token-user",
        "is_active": True,
        "auth_method": "bearer_token",
    }


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[dict]:
    """
    Return user context if a valid Bearer token is present, None otherwise.
    """
    if credentials is None:
        return None
    try:
        _validate_token(credentials)
        return {
            "id": "token-user",
            "email": "token-user@app.local",
            "username": "token-user",
            "is_active": True,
            "auth_method": "bearer_token",
        }
    except HTTPException:
        return None


def get_user_id(
    current_user: dict = Depends(get_current_user),
) -> str:
    """Get current user's ID."""
    return str(current_user["id"])


# Type aliases for dependency injection
CurrentUser = Annotated[dict, Depends(get_current_user)]
OptionalUser = Annotated[Optional[dict], Depends(get_optional_user)]
UserId = Annotated[str, Depends(get_user_id)]
DBSession = Annotated[Session, Depends(get_db)]


class RateLimiter:
    """
    In-memory rate limiting dependency

    Features:
    - Sliding window rate limiting
    - IP-based and user-based limiting
    - Configurable requests per window
    """

    def __init__(self, requests: int = 100, window: int = 60, per_user: bool = False):
        self.requests = requests
        self.window = window
        self.per_user = per_user
        self._in_memory_cache: dict[str, list[float]] = {}

    def __call__(self, request: Request, current_user: Optional[dict] = None):
        """Check rate limit for the request"""
        return self._check_memory_rate_limit(request, current_user)

    def _check_memory_rate_limit(self, request: Request, current_user: Optional[dict] = None) -> bool:
        if self.per_user and current_user:
            key = f"user:{current_user['id']}"
        else:
            key = f"ip:{self._get_client_ip(request)}"

        current_time = time.time()
        window_start = current_time - self.window

        if key not in self._in_memory_cache:
            self._in_memory_cache[key] = []

        self._in_memory_cache[key] = [
            timestamp for timestamp in self._in_memory_cache[key]
            if timestamp > window_start
        ]

        if len(self._in_memory_cache[key]) >= self.requests:
            from app.exceptions import RateLimitError
            raise RateLimitError(
                message=f"Rate limit exceeded: {len(self._in_memory_cache[key])}/{self.requests} requests per {self.window}s"
            )

        self._in_memory_cache[key].append(current_time)
        return True

    def _get_client_ip(self, request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


def get_rate_limiter(requests: int = 100, window: int = 60) -> RateLimiter:
    """Factory for rate limiter dependency"""
    return RateLimiter(requests=requests, window=window)


class PaginationParams:
    """
    Advanced pagination parameters with cursor support
    """

    def __init__(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        cursor: Optional[str] = None,
        use_cursor: bool = False
    ):
        self.skip = max(0, skip)
        self.limit = min(max(1, limit), 1000)
        self.order_by = order_by
        self.order_desc = order_desc
        self.cursor = cursor
        self.use_cursor = use_cursor or cursor is not None

        if self.skip > 10000 and not self.use_cursor:
            logger.warning(f"Large offset detected ({self.skip}). Consider using cursor-based pagination for better performance.")

    def encode_cursor(self, value: Any) -> str:
        import base64
        import json
        cursor_data = {"value": str(value), "order_desc": self.order_desc}
        cursor_json = json.dumps(cursor_data)
        return base64.urlsafe_b64encode(cursor_json.encode()).decode()

    def decode_cursor(self) -> tuple[Any, bool]:
        if not self.cursor:
            return None, self.order_desc

        try:
            import base64
            import json
            cursor_json = base64.urlsafe_b64decode(self.cursor.encode()).decode()
            cursor_data = json.loads(cursor_json)
            return cursor_data["value"], cursor_data["order_desc"]
        except Exception as e:
            logger.warning(f"Invalid cursor format: {e}")
            return None, self.order_desc


class FilterParams:
    """Common filter parameters"""

    def __init__(
        self,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None
    ):
        self.search = search
        self.is_active = is_active
        self.created_after = created_after
        self.created_before = created_before


# Dependency shortcuts
Pagination = Annotated[PaginationParams, Depends()]
Filters = Annotated[FilterParams, Depends()]
