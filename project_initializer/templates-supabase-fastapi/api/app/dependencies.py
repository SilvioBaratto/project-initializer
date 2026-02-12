"""Global dependencies for the application"""

import time
from typing import Optional, Annotated, Any
from fastapi import Depends, Header, Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from supabase import create_client
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Database session dependencies
from app.database import get_db

# Supabase client (server-side, for JWT verification)
_supabase = create_client(settings.supabase_url, settings.supabase_publishable_key)

# Bearer token extractor
_bearer_scheme = HTTPBearer(auto_error=False)


# ===========================
# Supabase JWT Authentication
# ===========================

async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer_scheme)],
) -> dict:
    """
    Verify the Supabase JWT and return the authenticated user.

    Extracts the Bearer token from the Authorization header,
    calls Supabase auth.get_user(jwt) to validate it, and
    returns the user data.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = _supabase.auth.get_user(credentials.credentials)
        if not response or not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = response.user
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer_scheme)],
) -> Optional[dict]:
    """Return authenticated user if token is present, None otherwise."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def get_user_id(current_user: dict = Depends(get_current_user)) -> str:
    """Get current user's Supabase UUID."""
    return str(current_user["id"])


# Type aliases for dependency injection
CurrentUser = Annotated[dict, Depends(get_current_user)]
OptionalUser = Annotated[Optional[dict], Depends(get_optional_user)]
UserId = Annotated[str, Depends(get_user_id)]

# Database session shortcut
DBSession = Annotated[Session, Depends(get_db)]


# ===========================
# Rate Limiting
# ===========================

class RateLimiter:
    """In-memory rate limiting dependency"""

    def __init__(self, requests: int = 100, window: int = 60, per_user: bool = False):
        self.requests = requests
        self.window = window
        self.per_user = per_user
        self._in_memory_cache: dict[str, list[float]] = {}

    def __call__(self, request: Request, current_user: Optional[dict] = None):
        if self.per_user and current_user:
            key = f"user:{current_user['id']}"
        else:
            key = f"ip:{self._get_client_ip(request)}"

        current_time = time.time()
        window_start = current_time - self.window

        if key not in self._in_memory_cache:
            self._in_memory_cache[key] = []

        self._in_memory_cache[key] = [
            ts for ts in self._in_memory_cache[key] if ts > window_start
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
    return RateLimiter(requests=requests, window=window)


# ===========================
# Pagination
# ===========================

class PaginationParams:
    def __init__(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        order_desc: bool = False,
    ):
        self.skip = max(0, skip)
        self.limit = min(max(1, limit), 1000)
        self.order_by = order_by
        self.order_desc = order_desc


Pagination = Annotated[PaginationParams, Depends()]
