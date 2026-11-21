"""Lookup of the tenant's token signing keys, over PyJWT's JWKS client.

Anybody can send this API a token, so the lookup must not hand a stranger control
over the API's own traffic or over how an outage is reported. ``PyJWKClient`` on
its own reloads the key set for every token that names an unknown ``kid`` and
reports a malformed key document as an error type of its own. This adapter fixes
both: it reloads at most once per cooldown, and it answers every failure of the
key endpoint with the same domain error, so a caller sees a 503 and never a 401
or a 500 for a problem that is Entra's.
"""

import http.client
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any, Protocol

import jwt
from jwt.exceptions import PyJWKClientError, PyJWKSetError

from app.domain.exceptions import ExternalServiceError

SERVICE_NAME = "entra_jwks"

# PyJWT wraps only URLError and timeouts in PyJWKClientError. A reset connection,
# a broken HTTP exchange, a non-JSON answer (ValueError) and a key document
# without usable keys reach the caller as other types, and all of them mean that
# the key endpoint failed, not that the token is bad.
KEY_ENDPOINT_FAILURES = (
    PyJWKClientError,
    PyJWKSetError,
    OSError,
    ValueError,
    http.client.HTTPException,
)


class SigningKeyLike(Protocol):
    """A key that can verify a signature; ``jwt.PyJWK`` satisfies it."""

    key: Any


class PublishedSigningKey(SigningKeyLike, Protocol):
    """A key of the tenant's published key set, named by its ``kid``."""

    key_id: str | None


class SigningKeySource(Protocol):
    """The slice of ``PyJWKClient`` that the resolver reads."""

    def get_signing_keys(self, refresh: bool = False) -> Sequence[PublishedSigningKey]:
        """Return the signing keys of the key set.

        Args:
            refresh: Bypass the cache and load the key set again.
        """
        ...


class SigningKeyResolver(Protocol):
    """Finds the signing key that a token's header points at."""

    def get_signing_key_from_jwt(self, token: str) -> SigningKeyLike | None:
        """Find the key named by the token's ``kid`` header.

        Args:
            token: Raw token whose signature is not yet trusted.

        Returns:
            The key, or None when the tenant publishes no key with that id.

        Raises:
            jwt.InvalidTokenError: The token's header cannot be read.
            ExternalServiceError: The tenant's key endpoint is unreachable or
                answers with an error, a non-JSON body or a key set without
                usable keys.
        """
        ...


class CooldownSigningKeyResolver:
    """``SigningKeyResolver`` that reloads the key set at most once per cooldown.

    A token whose ``kid`` is not in the cached key set forces a reload, because
    Entra may have rotated its keys. The reload is claimed before it starts and
    stays claimed whether it works or not, so neither a burst of random ``kid``
    values nor a failing endpoint can make the API call Entra more than once per
    cooldown. A key rotated in during a cooldown is found after it ends.
    """

    def __init__(
        self,
        key_source: SigningKeySource,
        *,
        refresh_cooldown_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Configure the resolver.

        Args:
            key_source: Provider of the tenant's key set; it caches it between
                calls.
            refresh_cooldown_seconds: Minimum time between two forced reloads.
            clock: Monotonic time in seconds; tests supply their own.
        """
        self._key_source = key_source
        self._refresh_cooldown_seconds = refresh_cooldown_seconds
        self._clock = clock
        self._refresh_lock = threading.Lock()
        self._last_refresh_at: float | None = None

    def get_signing_key_from_jwt(self, token: str) -> SigningKeyLike | None:
        """Find the key named by the token's ``kid`` header.

        Args:
            token: Raw token whose signature is not yet trusted.

        Returns:
            The key, or None when no published key has that id, which includes a
            token without a usable ``kid`` and a miss that the cooldown does not
            allow to reload.

        Raises:
            jwt.InvalidTokenError: The token's header cannot be read.
            ExternalServiceError: The tenant's key endpoint is unreachable or
                answers with an error, a non-JSON body or a key set without
                usable keys.
        """
        key_id = jwt.get_unverified_header(token).get("kid")
        if not isinstance(key_id, str) or not key_id:
            return None
        cached_key = _find_key(self._published_keys(), key_id)
        if cached_key is not None or not self._claim_refresh():
            return cached_key
        return _find_key(self._published_keys(refresh=True), key_id)

    def _published_keys(
        self, *, refresh: bool = False
    ) -> Sequence[PublishedSigningKey]:
        try:
            return self._key_source.get_signing_keys(refresh=refresh)
        except KEY_ENDPOINT_FAILURES as error:
            # Only the class name is logged: the message can carry the endpoint
            # URL.
            raise ExternalServiceError(
                log_context={"service": SERVICE_NAME, "error": type(error).__name__}
            ) from error

    def _claim_refresh(self) -> bool:
        with self._refresh_lock:
            if self._cooling_down():
                return False
            self._last_refresh_at = self._clock()
            return True

    def _cooling_down(self) -> bool:
        if self._last_refresh_at is None:
            return False
        return self._clock() - self._last_refresh_at < self._refresh_cooldown_seconds


def _find_key(
    keys: Sequence[PublishedSigningKey], key_id: str
) -> PublishedSigningKey | None:
    return next((key for key in keys if key.key_id == key_id), None)
