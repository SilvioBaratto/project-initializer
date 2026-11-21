"""Extraction of a bearer token from the ``Authorization`` header.

Token, Supabase and Entra variants share this step and differ only in how they
verify the token, so the header handling lives in one place.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.exceptions import AuthenticationError

# Real tokens are far shorter. The cap keeps an attacker from making the server
# hash or parse megabytes of header on every request.
MAX_BEARER_TOKEN_LENGTH = 8192

# ``auto_error=False`` so a missing header becomes our AuthenticationError and
# therefore the standard error envelope instead of FastAPI's own 401 body
# (``{"detail": "Not authenticated"}``).
bearer_scheme = HTTPBearer(auto_error=False)


def require_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    """Return the bearer token of the request.

    Args:
        credentials: Parsed ``Authorization`` header, or None when it is absent
            or does not use the ``Bearer`` scheme.

    Returns:
        The raw token, without the ``Bearer`` prefix.

    Raises:
        AuthenticationError: The header is missing, uses another scheme, holds an
            empty token or one longer than ``MAX_BEARER_TOKEN_LENGTH``.
    """
    if credentials is None:
        raise AuthenticationError()
    token = credentials.credentials
    if not token or len(token) > MAX_BEARER_TOKEN_LENGTH:
        raise AuthenticationError()
    return token


BearerToken = Annotated[str, Depends(require_bearer_token)]
