"""Token verifier port: turns a bearer token into an authenticated principal."""

from typing import Protocol, runtime_checkable

from app.domain.entities.authenticated_user import AuthenticatedUser


@runtime_checkable
class TokenVerifierPort(Protocol):
    """Validates a bearer token against one identity provider."""

    def verify(self, token: str) -> AuthenticatedUser:
        """Validate a token and identify its owner.

        Args:
            token: Raw bearer token, without the ``Bearer`` prefix.

        Returns:
            The principal the token belongs to.

        Raises:
            AuthenticationError: The token is invalid, expired or unknown.
            AuthorizationError: The token is valid but lacks a required scope.
            ExternalServiceError: The identity provider could not be reached.
        """
        ...
