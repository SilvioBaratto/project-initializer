"""Validation of Microsoft Entra ID v2 access tokens, in-process.

A token is checked against the tenant's public signing keys, so no call to
Entra happens per request once the keys are cached. Every rejection answers the
caller with the same generic 401; the reason is kept in the error's log
context, together with the object and tenant ids once the signature has proved
those claims genuine. Tokens and email addresses are never logged.
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Self

import jwt
from jwt import PyJWKClient

from app.domain.entities.authenticated_user import AuthenticatedUser
from app.domain.exceptions import AuthenticationError, AuthorizationError
from app.infrastructure.auth.entra_jwks import (
    CooldownSigningKeyResolver,
    SigningKeyLike,
    SigningKeyResolver,
)
from app.infrastructure.auth_settings import AuthSettings, normalize_scope

# Only RS256 is accepted. Allowing the token header to pick the algorithm is how
# "alg: none" and HMAC-with-the-public-key forgeries get through.
ENTRA_SIGNING_ALGORITHMS = ("RS256",)
REQUIRED_CLAIMS = ("exp", "iat", "iss", "aud")
ENTRA_AUTH_METHOD = "entra"
# Entra and this server do not share a clock; without leeway a token issued a
# moment ago can look as if it came from the future. The same margin applies to
# ``exp``, which is the usual trade-off.
CLOCK_SKEW_LEEWAY_SECONDS = 30


class RejectionReason(StrEnum):
    """Why a token was rejected; goes to the log, never to the caller."""

    UNKNOWN_SIGNING_KEY = "unknown_signing_key"
    MALFORMED_TOKEN = "malformed_token"
    BAD_SIGNATURE = "bad_signature"
    DISALLOWED_ALGORITHM = "disallowed_algorithm"
    EXPIRED = "expired"
    NOT_YET_VALID = "not_yet_valid"
    WRONG_ISSUER = "wrong_issuer"
    WRONG_AUDIENCE = "wrong_audience"
    MISSING_CLAIM = "missing_claim"
    INVALID_TOKEN = "invalid_token"
    WRONG_TENANT = "wrong_tenant"
    MISSING_SUBJECT = "missing_subject"
    MISSING_SCOPE = "missing_scope"


# Subclasses come before their parents: the first match wins.
_DECODE_FAILURE_REASONS: tuple[tuple[type[Exception], RejectionReason], ...] = (
    (jwt.ExpiredSignatureError, RejectionReason.EXPIRED),
    (jwt.InvalidAudienceError, RejectionReason.WRONG_AUDIENCE),
    (jwt.InvalidIssuerError, RejectionReason.WRONG_ISSUER),
    (jwt.MissingRequiredClaimError, RejectionReason.MISSING_CLAIM),
    (jwt.InvalidAlgorithmError, RejectionReason.DISALLOWED_ALGORITHM),
    (jwt.InvalidSignatureError, RejectionReason.BAD_SIGNATURE),
    (jwt.ImmatureSignatureError, RejectionReason.NOT_YET_VALID),
    (jwt.DecodeError, RejectionReason.MALFORMED_TOKEN),
)


def expected_audiences(auth_settings: AuthSettings) -> tuple[str, ...]:
    """List the audience values this API accepts.

    A v2 access token carries whichever form the app registration advertises,
    so the bare client id, the ``api://`` form and any configured audience are
    all honoured.

    Args:
        auth_settings: Source of the client id and the optional extra audience.

    Returns:
        The distinct non-empty audiences, in a stable order.
    """
    client_id = auth_settings.entra_api_client_id
    candidates = (
        client_id,
        f"api://{client_id}" if client_id else "",
        auth_settings.entra_api_audience,
    )
    return tuple(dict.fromkeys(audience for audience in candidates if audience))


def _rejected(reason: RejectionReason, **identity: object) -> AuthenticationError:
    return AuthenticationError(log_context={"reason": reason, **identity})


def _text_claim(claims: dict[str, Any], name: str) -> str | None:
    value = claims.get(name)
    return value if isinstance(value, str) and value else None


def _role_names(claims: dict[str, Any]) -> tuple[str, ...]:
    roles = claims.get("roles")
    if not isinstance(roles, list):
        return ()
    return tuple(role for role in roles if isinstance(role, str))


class EntraTokenVerifier:
    """``TokenVerifierPort`` for access tokens issued by one Entra tenant."""

    def __init__(
        self,
        *,
        signing_keys: SigningKeyResolver,
        tenant_id: str,
        audiences: Sequence[str],
        issuer: str,
        required_scope: str,
    ) -> None:
        """Configure the verifier.

        Args:
            signing_keys: Resolver of the tenant's public signing keys.
            tenant_id: Tenant that must have issued the token (``tid`` claim).
            audiences: Accepted ``aud`` values; the token must carry one of them.
            issuer: Expected ``iss`` claim.
            required_scope: Scope the token must grant, as a bare name or a full
                URI.

        Raises:
            ValueError: No audience is given or the scope is empty. Failing
                here keeps a misconfiguration from silently disabling a check.
        """
        if not audiences:
            raise ValueError("at least one accepted audience is required")
        scope_name = normalize_scope(required_scope)
        if not scope_name:
            raise ValueError("a non-empty required scope is needed")
        self._signing_keys = signing_keys
        self._tenant_id = tenant_id
        self._audiences = list(audiences)
        self._issuer = issuer
        self._required_scope = scope_name

    @classmethod
    def from_settings(cls, auth_settings: AuthSettings) -> Self:
        """Build the verifier for the configured tenant.

        The key client carries an explicit timeout, so a slow or unreachable
        Entra cannot hold a worker thread indefinitely, and it caches the key
        set between requests. The resolver around it limits how often an unknown
        ``kid`` may force a reload.

        Args:
            auth_settings: Source of the tenant, audiences, scope, timeout and
                refresh cooldown.

        Returns:
            A verifier that fetches signing keys over HTTPS from the authority.

        Raises:
            ValueError: No audience is configured.
        """
        key_client = PyJWKClient(
            auth_settings.entra_jwks_url, timeout=auth_settings.entra_jwks_timeout
        )
        return cls(
            signing_keys=CooldownSigningKeyResolver(
                key_client,
                refresh_cooldown_seconds=auth_settings.entra_jwks_refresh_cooldown,
            ),
            tenant_id=auth_settings.entra_tenant_id,
            audiences=expected_audiences(auth_settings),
            issuer=auth_settings.entra_issuer,
            required_scope=auth_settings.entra_api_scope,
        )

    def verify(self, token: str) -> AuthenticatedUser:
        """Validate an access token and identify its owner.

        Args:
            token: Raw bearer token issued by the tenant.

        Returns:
            The principal. ``id`` is the ``oid`` claim, else ``sub``; ``roles``
            holds every app role of the ``roles`` claim; ``username`` is the
            ``preferred_username`` claim. ``email`` comes from the ``email``
            claim alone: ``preferred_username`` is a mutable sign-in name that
            need not be an address, so it is never promoted to ``email`` where
            code might use that to link or authorise an account.

        Raises:
            AuthenticationError: The token is malformed, forged, expired, meant
                for another audience, issuer or tenant, or has no subject.
            AuthorizationError: The token is valid but does not grant the
                required scope, as for an app-only token.
            ExternalServiceError: The tenant's signing keys could not be fetched
                or the key endpoint answered with something unusable.
        """
        claims = self._decode(token)
        identity = {"oid": claims.get("oid"), "tid": claims.get("tid")}
        if claims.get("tid") != self._tenant_id:
            raise _rejected(RejectionReason.WRONG_TENANT, **identity)
        subject = _text_claim(claims, "oid") or _text_claim(claims, "sub")
        if subject is None:
            raise _rejected(RejectionReason.MISSING_SUBJECT, **identity)
        self._require_scope(claims, identity)
        return self._principal(claims, subject)

    def _decode(self, token: str) -> dict[str, Any]:
        signing_key = self._signing_key_for(token)
        try:
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=list(ENTRA_SIGNING_ALGORITHMS),
                audience=self._audiences,
                issuer=self._issuer,
                leeway=CLOCK_SKEW_LEEWAY_SECONDS,
                options={"require": list(REQUIRED_CLAIMS)},
            )
        except jwt.InvalidTokenError as error:
            reason = next(
                (
                    mapped
                    for error_type, mapped in _DECODE_FAILURE_REASONS
                    if isinstance(error, error_type)
                ),
                RejectionReason.INVALID_TOKEN,
            )
            raise _rejected(reason) from error

    def _signing_key_for(self, token: str) -> SigningKeyLike:
        try:
            signing_key = self._signing_keys.get_signing_key_from_jwt(token)
        except jwt.InvalidTokenError as error:
            raise _rejected(RejectionReason.MALFORMED_TOKEN) from error
        if signing_key is None:
            raise _rejected(RejectionReason.UNKNOWN_SIGNING_KEY)
        return signing_key

    def _require_scope(
        self, claims: dict[str, Any], identity: dict[str, object]
    ) -> None:
        # ``scp`` is a space-separated list of bare scope names. Entries are
        # compared whole, so a scope that merely starts with the required name
        # does not satisfy it.
        granted = claims.get("scp")
        if isinstance(granted, str) and self._required_scope in granted.split():
            return
        raise AuthorizationError(
            log_context={"reason": RejectionReason.MISSING_SCOPE, **identity}
        )

    @staticmethod
    def _principal(claims: dict[str, Any], subject: str) -> AuthenticatedUser:
        preferred_username = _text_claim(claims, "preferred_username")
        return AuthenticatedUser(
            id=subject,
            auth_method=ENTRA_AUTH_METHOD,
            email=_text_claim(claims, "email"),
            username=preferred_username,
            roles=_role_names(claims),
        )
