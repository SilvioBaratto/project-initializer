"""Global dependencies for the application — token-based authentication"""

import secrets
import time
import logging
from typing import Optional, Annotated, Any

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
    OAuth2PasswordBearer,
)
from sqlalchemy.orm import Session

from app.infrastructure.settings import settings
from app.infrastructure.security import decode_token
from app.infrastructure.database import get_db
from app.infrastructure.orm import User
from jose import JWTError

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
        "email": "token-user@example.com",
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
            "email": "token-user@example.com",
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


# ===========================
# JWT Authentication (opt-in OAuth2-password flow)
# ===========================
# ALTERNATIVE to the static AUTH_TOKEN mode above. The static
# get_current_user / CurrentUser remain the default; these JWT deps are
# exposed under DISTINCT names + the JWTUser / ActiveJWTUser aliases so the
# two modes never collide.
# tokenUrl has NO leading slash so it composes with the /api/v1 app prefix.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token", auto_error=False)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user_jwt(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode the bearer JWT, load the User by `sub`, or 401."""
    if token is None:
        raise _CREDENTIALS_EXC
    user = _load_user_from_token(token, db)
    if user is None:
        raise _CREDENTIALS_EXC
    return user


def _load_user_from_token(token: str, db: Session) -> Optional[User]:
    """Return the User named by the JWT `sub`, or None on any failure."""
    try:
        payload = decode_token(token, settings.jwt_secret_key, settings.jwt_algorithm)
    except JWTError:
        return None
    subject = payload.get("sub")
    if subject is None:
        return None
    return db.get(User, subject)


def get_current_active_user(
    current_user: User = Depends(get_current_user_jwt),
) -> User:
    """Require the JWT-authenticated user to be active, else 400."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


# JWT dependency aliases (distinct from the static CurrentUser default)
JWTUser = Annotated[User, Depends(get_current_user_jwt)]
ActiveJWTUser = Annotated[User, Depends(get_current_active_user)]


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

    def _check_memory_rate_limit(
        self, request: Request, current_user: Optional[dict] = None
    ) -> bool:
        if self.per_user and current_user:
            key = f"user:{current_user['id']}"
        else:
            key = f"ip:{self._get_client_ip(request)}"

        current_time = time.time()
        window_start = current_time - self.window

        if key not in self._in_memory_cache:
            self._in_memory_cache[key] = []

        self._in_memory_cache[key] = [
            timestamp
            for timestamp in self._in_memory_cache[key]
            if timestamp > window_start
        ]

        if len(self._in_memory_cache[key]) >= self.requests:
            from app.domain.exceptions import RateLimitError

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
        skip: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        cursor: Optional[str] = None,
        use_cursor: bool = False,
    ):
        # Query(ge=0)/(ge=1, le=100) enforce bounds before __init__ runs and
        # surface them in OpenAPI, so no in-body clamp is needed here.
        self.skip = skip
        self.limit = limit
        self.order_by = order_by
        self.order_desc = order_desc
        self.cursor = cursor
        self.use_cursor = use_cursor or cursor is not None

        if self.skip > 10000 and not self.use_cursor:
            logger.warning(
                f"Large offset detected ({self.skip}). Consider using cursor-based pagination for better performance."
            )

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


# Dependency shortcuts
Pagination = Annotated[PaginationParams, Depends()]
