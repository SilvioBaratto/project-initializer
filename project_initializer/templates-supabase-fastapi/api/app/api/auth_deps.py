"""Authentication dependency of the Supabase variant.

This module replaces the base auth seam and exports the same names, so routes and
the role guard do not learn which provider is behind them. The caller's bearer
token is verified by Supabase Auth.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.api.bearer import BearerToken
from app.domain.entities.authenticated_user import AuthenticatedUser
from app.domain.ports.token_verifier import TokenVerifierPort
from app.infrastructure.auth.supabase import SupabaseTokenVerifier
from app.infrastructure.settings import settings


@lru_cache(maxsize=1)
def get_token_verifier() -> TokenVerifierPort:
    """Provide the process-wide verifier of Supabase access tokens.

    Built on first use and then reused, because it owns an HTTP connection pool.
    Tests replace it through ``app.dependency_overrides``.

    Returns:
        The verifier configured from the application settings.

    Raises:
        SupabaseException: The Supabase URL or key is not configured.
    """
    return SupabaseTokenVerifier.from_settings(settings)


def get_current_user(
    token: BearerToken,
    verifier: Annotated[TokenVerifierPort, Depends(get_token_verifier)],
) -> AuthenticatedUser:
    """Resolve the caller from the bearer token.

    It is a plain ``def`` because verification blocks on a network call, so
    FastAPI runs it in a worker thread instead of stalling the event loop.

    Args:
        token: Bearer token of the request; a missing or unusable header is
            rejected before the verifier is touched.
        verifier: Verifier of Supabase access tokens.

    Returns:
        The authenticated principal.

    Raises:
        AuthenticationError: The token is missing, invalid or expired.
        ExternalServiceError: Supabase Auth is unavailable.
    """
    return verifier.verify(token)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
