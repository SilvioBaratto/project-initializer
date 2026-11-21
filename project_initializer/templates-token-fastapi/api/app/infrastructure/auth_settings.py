"""Authentication settings of the token variant.

``Settings`` inherits from this class, so ``AUTH_TOKEN``, ``JWT_SECRET_KEY``,
``JWT_ALGORITHM`` and ``ACCESS_TOKEN_EXPIRE_MINUTES`` are read from the
environment like every other setting. The secrets default to empty, which keeps
a fresh checkout importable; an empty secret never authenticates anyone, and a
production-like stage refuses to start with one. A non-empty secret must be
strong at every stage, because a development server is often reachable from the
network.
"""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_STATIC_TOKEN_LENGTH = 16
MIN_JWT_SECRET_LENGTH = 32
PLACEHOLDER_SECRETS = frozenset({"changeme", "change-me", "secret"})

JwtAlgorithm = Literal["HS256", "HS384", "HS512"]
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
MIN_ACCESS_TOKEN_EXPIRE_MINUTES = 1
MAX_ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60


def _require_strong_secret(
    name: str, secret: SecretStr, minimum_length: int, *, required: bool
) -> None:
    value = secret.get_secret_value()
    if not value and not required:
        return
    if value.strip().lower() in PLACEHOLDER_SECRETS or len(value) < minimum_length:
        raise ValueError(
            f"{name} must be set to a generated value of at least "
            f"{minimum_length} characters, not a placeholder"
        )


class AuthSettings(BaseSettings):
    """Credentials and token policy of the token authentication variant.

    Attributes:
        auth_token: Shared secret that clients send as the bearer token to reach
            protected routes. Empty means no token is accepted, so the guarded
            routes answer 401.
        jwt_secret_key: Key that signs and verifies JWT access tokens. Empty
            switches login and the JWT guard off, so they answer 503;
            registration does not need it.
        jwt_algorithm: HMAC algorithm of the JWTs. Asymmetric algorithms are
            excluded because the one secret both signs and verifies.
        access_token_expire_minutes: Lifetime of an issued JWT, one minute up to
            one day.
    """

    # Without this a validation failure at startup prints the raw environment
    # values, so a rejected secret would land in the logs in clear text. The
    # setting is inherited by ``Settings``.
    model_config = SettingsConfigDict(hide_input_in_errors=True)

    auth_token: SecretStr = SecretStr("")
    jwt_secret_key: SecretStr = SecretStr("")
    jwt_algorithm: JwtAlgorithm = "HS256"
    access_token_expire_minutes: int = Field(
        default=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
        ge=MIN_ACCESS_TOKEN_EXPIRE_MINUTES,
        le=MAX_ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    def validate_auth_secrets(self, *, production_like: bool) -> None:
        """Reject secrets that must not run in the current deployment stage.

        An empty secret switches its feature off and is accepted in development
        and test, so a checkout runs without setup. A non-empty secret must meet
        its minimum length and not be a placeholder at every stage.

        Args:
            production_like: True for the staging and production environments,
                where an empty secret is refused too.

        Raises:
            ValueError: A secret is a known placeholder or shorter than its
                minimum length, or is empty in a production-like stage. The
                message names the setting, never its value.
        """
        _require_strong_secret(
            "AUTH_TOKEN",
            self.auth_token,
            MIN_STATIC_TOKEN_LENGTH,
            required=production_like,
        )
        _require_strong_secret(
            "JWT_SECRET_KEY",
            self.jwt_secret_key,
            MIN_JWT_SECRET_LENGTH,
            required=production_like,
        )
