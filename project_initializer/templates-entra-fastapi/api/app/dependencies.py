"""Global dependencies for the application"""

import logging
import time
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

# JWKS client — module-level singleton; PyJWKClient caches keys and auto-refreshes
# on key rotation (no hard-coded schedule needed).
_jwks_client = PyJWKClient(settings.entra_jwks_url)

# Bearer token extractor
_bearer_scheme = HTTPBearer(auto_error=False)


# ===========================
# Entra v2 JWT Authentication
# ===========================


def _expected_audiences() -> list[str]:
    """Accept the bare GUID, the api://<client-id> URI, and any configured audience.

    A v2 access token's aud carries whichever form the app registration
    advertises, so all three are honoured to avoid rejecting a valid token.
    """
    candidates = [
        settings.entra_api_client_id,
        f"api://{settings.entra_api_client_id}",
        settings.entra_api_audience,
    ]
    return [aud for aud in dict.fromkeys(candidates) if aud]


def _validate_token(token: str) -> dict:
    """Validate an Entra v2 RS256 JWT and return its claims.

    Raises HTTPException 401 on any signature/claim failure,
    HTTPException 403 when the required scp scope is missing.
    """
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
    except Exception as exc:
        logger.warning("JWKS key fetch failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims: dict = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=_expected_audiences(),
            issuer=settings.entra_issuer,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _verify_tenant(claims)
    _verify_scope(claims)
    return claims


def _verify_tenant(claims: dict) -> None:
    """Raise 401 when the token was issued by a different tenant."""
    if claims.get("tid") != settings.entra_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: wrong tenant",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _verify_scope(claims: dict) -> None:
    """Raise 403 when the required scope is absent from the scp claim.

    Tokens without an scp claim (e.g. app-only flows) also return 403,
    not 500 — defensive .get() prevents KeyError.
    """
    granted: list[str] = claims.get("scp", "").split()
    if settings.entra_api_scope and settings.entra_api_scope not in granted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient scope",
        )


async def get_current_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(_bearer_scheme)
    ],
) -> dict:
    """Verify the Entra v2 JWT and return the authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = _validate_token(credentials.credentials)
    return {
        "id": claims.get("oid") or claims.get("sub", ""),
        "email": claims.get("preferred_username") or claims.get("email", ""),
        "role": claims.get("roles", ["authenticated"])[0]
        if claims.get("roles")
        else "authenticated",
    }


async def get_optional_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(_bearer_scheme)
    ],
) -> Optional[dict]:
    """Return authenticated user if token is present, None otherwise."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def get_user_id(current_user: dict = Depends(get_current_user)) -> str:
    """Get current user's Entra object ID."""
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
        key = self._build_key(request, current_user)
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

    def _build_key(self, request: Request, current_user: Optional[dict]) -> str:
        if self.per_user and current_user:
            return f"user:{current_user['id']}"
        return f"ip:{self._get_client_ip(request)}"

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
        skip: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        order_by: Optional[str] = None,
        order_desc: bool = False,
    ):
        self.skip = skip
        self.limit = limit
        self.order_by = order_by
        self.order_desc = order_desc


Pagination = Annotated[PaginationParams, Depends()]
