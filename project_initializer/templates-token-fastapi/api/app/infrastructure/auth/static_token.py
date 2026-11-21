"""Verifier for the shared static bearer token."""

import hashlib
import hmac

from pydantic import SecretStr

from app.domain.entities.authenticated_user import AuthenticatedUser
from app.domain.exceptions import AuthenticationError

STATIC_TOKEN_USER_ID = "token-user"
STATIC_TOKEN_AUTH_METHOD = "static_token"


def _digest(text: str) -> bytes:
    # surrogatepass keeps the digest total: a lone surrogate can reach this point
    # through a JSON body, and strict UTF-8 would raise instead of failing the match.
    return hashlib.sha256(text.encode("utf-8", errors="surrogatepass")).digest()


def tokens_match(candidate: str, expected: str) -> bool:
    """Compare a presented token with the configured one in constant time.

    Both sides are hashed first. ``hmac.compare_digest`` raises on a ``str`` that
    holds non-ASCII characters, and hashing fixes the length of what is compared,
    so neither the content nor the length of the secret can be probed.

    Args:
        candidate: Token presented by the client; any text is accepted.
        expected: The configured token. An empty value means the feature is
            switched off, so it matches nothing, not even an empty candidate.

    Returns:
        True only when the two are identical and ``expected`` is not empty.
    """
    if not expected:
        return False
    return hmac.compare_digest(_digest(candidate), _digest(expected))


class StaticTokenVerifier:
    """Admits every caller that presents the configured shared secret.

    The secret identifies a machine or a trusted client, not a person, so every
    match resolves to the same principal.
    """

    def __init__(self, expected_token: SecretStr) -> None:
        """Bind the verifier to the configured secret.

        Args:
            expected_token: The shared secret. An empty secret rejects every token.
        """
        self._expected_token = expected_token

    def verify(self, token: str) -> AuthenticatedUser:
        """Check the presented token against the configured secret.

        Args:
            token: Raw bearer token, without the ``Bearer`` prefix.

        Returns:
            The static-token principal.

        Raises:
            AuthenticationError: The token does not match. A new error is built
                on every call, so no traceback is shared between requests.
        """
        if not tokens_match(token, self._expected_token.get_secret_value()):
            raise AuthenticationError(log_context={"reason": "static_token_mismatch"})
        return AuthenticatedUser(
            id=STATIC_TOKEN_USER_ID,
            auth_method=STATIC_TOKEN_AUTH_METHOD,
            username=STATIC_TOKEN_USER_ID,
        )
