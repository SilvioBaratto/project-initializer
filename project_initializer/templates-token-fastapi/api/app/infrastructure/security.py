"""Adapters of the credential ports: bcrypt password hashing and JWT access tokens.

``bcrypt`` is called directly, without a wrapper library. Since 5.0 it raises
``ValueError`` for a password over 72 bytes (4.x ignored everything past the
72nd byte) and for a malformed hash. The hasher checks both before calling it, so
``verify`` never raises and never truncates, and ``hash`` refuses a password
that bcrypt could not hash in full.
"""

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Self

import bcrypt
from jose import JWTError, jwt
from pydantic import SecretStr

from app.domain.constants import PASSWORD_MAX_BYTES
from app.domain.exceptions import AuthenticationError
from app.infrastructure.auth_settings import AuthSettings, JwtAlgorithm

BCRYPT_COST_FACTOR = 12
# Anything that is not a canonical bcrypt hash must not reach ``checkpw``: it
# raises ``ValueError("Invalid salt")`` for a truncated hash, a cost outside
# 4..31 and a salt whose last character carries bits the 16-byte salt does not
# have (only ``.``, ``O``, ``e`` and ``u`` are legal there). Left uncaught that
# turns a login into a 500 and skips the timing comparison.
BCRYPT_HASH_PATTERN = re.compile(
    rb"\$2[aby]\$(0[4-9]|[12][0-9]|3[01])\$[./A-Za-z0-9]{21}[.Oeu][./A-Za-z0-9]{31}"
)
TIMING_REFERENCE_PASSWORD = b"timing-reference-password"
PASSWORD_ENCODING = "utf-8"
# Text that cannot be encoded strictly (a lone surrogate) must still hash and
# compare, so the encoding never raises on untrusted input.
ENCODING_ERRORS = "surrogatepass"

JWT_REQUIRED_CLAIM_OPTIONS = {"require_exp": True, "require_sub": True}


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BcryptPasswordHasher:
    """Hashes passwords with bcrypt and a fresh salt for every hash."""

    def __init__(self, rounds: int = BCRYPT_COST_FACTOR) -> None:
        """Choose the work factor.

        Args:
            rounds: bcrypt cost factor; each increment doubles the time one hash
                takes. Lower it in tests only.
        """
        self._rounds = rounds

    @cached_property
    def _timing_reference_hash(self) -> bytes:
        # Built lazily with this instance's own cost, so checking a missing
        # account takes as long as checking a real one.
        return bcrypt.hashpw(TIMING_REFERENCE_PASSWORD, bcrypt.gensalt(self._rounds))

    def hash(self, password: str) -> str:
        """Hash a password.

        Args:
            password: Plain-text password.

        Returns:
            A ``$2b$`` hash that carries its salt and cost factor.

        Raises:
            ValueError: The password is longer than ``PASSWORD_MAX_BYTES`` bytes
                once encoded.
        """
        encoded = password.encode(PASSWORD_ENCODING, errors=ENCODING_ERRORS)
        if len(encoded) > PASSWORD_MAX_BYTES:
            raise ValueError(f"password exceeds {PASSWORD_MAX_BYTES} bytes")
        return bcrypt.hashpw(encoded, bcrypt.gensalt(self._rounds)).decode("ascii")

    def verify(self, password: str, password_hash: str | None) -> bool:
        """Check a candidate password against a stored hash.

        Exactly one bcrypt comparison runs whatever the input, so a missing,
        empty or malformed hash costs as much as a real mismatch.

        Args:
            password: Plain-text candidate.
            password_hash: Stored bcrypt hash; None, empty or malformed never
                matches.

        Returns:
            True only for a well-formed hash that the password matches. A
            password longer than ``PASSWORD_MAX_BYTES`` bytes never matches,
            because no such password could have been hashed.
        """
        encoded = password.encode(PASSWORD_ENCODING, errors=ENCODING_ERRORS)
        stored = (password_hash or "").encode(PASSWORD_ENCODING, errors=ENCODING_ERRORS)
        usable_hash = BCRYPT_HASH_PATTERN.fullmatch(stored) is not None
        fits = len(encoded) <= PASSWORD_MAX_BYTES
        reference = stored if usable_hash else self._timing_reference_hash
        agrees = bcrypt.checkpw(encoded if fits else b"", reference)
        return usable_hash and fits and agrees


class JwtAccessTokenIssuer:
    """Signs and verifies HMAC JWT access tokens that carry the user id as ``sub``."""

    def __init__(
        self,
        secret_key: SecretStr,
        algorithm: JwtAlgorithm,
        expires_minutes: int,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """Configure the issuer.

        Args:
            secret_key: Key that signs and verifies every token.
            algorithm: HMAC algorithm. Only this one is accepted on verification,
                so a token signed with another algorithm, or with none, fails.
            expires_minutes: Lifetime of an issued token.
            clock: Source of the current time; tests inject a fixed one.

        Raises:
            ValueError: The secret key is empty. An empty key is a valid HMAC
                key, so signing with it would let anybody forge tokens.
        """
        if not secret_key.get_secret_value():
            raise ValueError("JWT_SECRET_KEY must be set to issue access tokens")
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expires_minutes = expires_minutes
        self._clock = clock

    @classmethod
    def from_settings(
        cls, auth_settings: AuthSettings, *, clock: Callable[[], datetime] = _utc_now
    ) -> Self:
        """Build the issuer from the application settings.

        Args:
            auth_settings: Settings that carry the key, algorithm and lifetime.
            clock: Source of the current time.

        Returns:
            A configured issuer.

        Raises:
            ValueError: The settings hold an empty secret key.
        """
        return cls(
            auth_settings.jwt_secret_key,
            auth_settings.jwt_algorithm,
            auth_settings.access_token_expire_minutes,
            clock=clock,
        )

    def issue(self, subject: str) -> str:
        """Sign a token for an account.

        Args:
            subject: Identifier of the account.

        Returns:
            A JWT with ``sub``, ``iat`` and an ``exp`` set to the configured
            lifetime from now.
        """
        issued_at = self._clock()
        claims = {
            "sub": subject,
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=self._expires_minutes),
        }
        return jwt.encode(
            claims, self._secret_key.get_secret_value(), algorithm=self._algorithm
        )

    def subject_of(self, token: str) -> str:
        """Verify a token and return its subject.

        Args:
            token: Encoded JWT received from a client.

        Returns:
            The ``sub`` claim.

        Raises:
            AuthenticationError: The token is malformed, has a bad signature, is
                expired, uses another algorithm or lacks ``exp`` or ``sub``.
                The failure class is logged; nothing about it reaches the client.
        """
        try:
            claims = jwt.decode(
                token,
                self._secret_key.get_secret_value(),
                algorithms=[self._algorithm],
                options=JWT_REQUIRED_CLAIM_OPTIONS,
            )
        # ValueError covers text that cannot be encoded, such as a lone surrogate.
        except (JWTError, ValueError) as error:
            raise AuthenticationError(
                log_context={"reason": type(error).__name__}
            ) from error
        return claims["sub"]
