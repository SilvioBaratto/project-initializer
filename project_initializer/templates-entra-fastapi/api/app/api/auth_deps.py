"""Authentication dependency of the Microsoft Entra ID variant.

This module replaces the base auth seam and exports the same names, so routes and
the role guard do not learn which provider is behind them. The caller's bearer
token is an Entra v2 access token, validated in-process.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.api.bearer import BearerToken
from app.domain.entities.authenticated_user import AuthenticatedUser
from app.domain.ports.token_verifier import TokenVerifierPort
from app.infrastructure.auth.entra import EntraTokenVerifier
from app.infrastructure.settings import settings


@lru_cache(maxsize=1)
def get_token_verifier() -> TokenVerifierPort:
    """Provide the process-wide verifier of Entra access tokens.

    Built on first use and then reused, because it caches the tenant's signing
    keys. Tests replace it through ``app.dependency_overrides``.

    Returns:
        The verifier configured from the application settings.

    Raises:
        ValueError: No audience is configured, which only a local stage allows:
            ``Settings`` refuses an empty client id in staging and production,
            and refuses a malformed id or scope in every stage.
    """
    return EntraTokenVerifier.from_settings(settings)


def get_current_user(
    token: BearerToken,
    verifier: Annotated[TokenVerifierPort, Depends(get_token_verifier)],
) -> AuthenticatedUser:
    """Resolve the caller from the bearer token.

    It is a plain ``def`` because a cache miss makes verification fetch the
    signing keys over the network, so FastAPI runs it in a worker thread
    instead of stalling the event loop.

    Args:
        token: Bearer token of the request; a missing or unusable header is
            rejected before the verifier is touched.
        verifier: Verifier of Entra access tokens.

    Returns:
        The authenticated principal.

    Raises:
        AuthenticationError: The token is missing or invalid.
        AuthorizationError: The token does not grant the required scope.
        ExternalServiceError: The tenant's signing keys are unavailable.
    """
    return verifier.verify(token)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
