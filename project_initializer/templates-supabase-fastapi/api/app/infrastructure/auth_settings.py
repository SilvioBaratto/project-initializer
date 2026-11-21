"""Authentication settings of the Supabase variant.

Supabase Auth judges the bearer tokens, so the API needs only the project URL and
the publishable key. There is no secret (service-role) key setting on purpose:
this service never has to bypass row-level security.
"""

from urllib.parse import urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings

# Every placeholder the generated ``.env`` and the docs use starts with "your-".
PLACEHOLDER_MARKER = "your-"
REQUIRED_URL_SCHEME = "https"
# Supabase's secret keys bypass row-level security. A publishable key is the only
# kind this service is meant to hold.
SECRET_KEY_PREFIX = "sb_secret_"
DEFAULT_AUTH_TIMEOUT_SECONDS = 5.0
MAX_AUTH_TIMEOUT_SECONDS = 30.0


def _is_unset_or_placeholder(value: str) -> bool:
    return not value.strip() or PLACEHOLDER_MARKER in value.lower()


class AuthSettings(BaseSettings):
    """Supabase configuration shared into ``Settings``.

    Both connection values default to empty so tools can import the settings
    without a ``.env``. An empty value is rejected in production-like stages. In
    other stages the first token verification raises the Supabase client's
    configuration error, which the application answers with a generic 500.

    Attributes:
        supabase_url: Project URL, such as ``https://<ref>.supabase.co``.
        supabase_publishable_key: Publishable (``sb_publishable_...``) key. It is
            public by design and only identifies the project to Supabase Auth.
        supabase_auth_timeout: Seconds to wait for Supabase Auth to answer a token
            check. It bounds how long one request can occupy a worker thread.
    """

    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_auth_timeout: float = Field(
        default=DEFAULT_AUTH_TIMEOUT_SECONDS, gt=0, le=MAX_AUTH_TIMEOUT_SECONDS
    )

    def validate_auth_secrets(self, *, production_like: bool) -> None:
        """Reject a missing or placeholder Supabase project in a deployed stage.

        Args:
            production_like: True for the staging and production environments.
                Development and test accept any value, so a fresh scaffold runs
                before the project is configured.

        Raises:
            ValueError: The URL or the key is empty or still a placeholder, the
                URL does not use https, or the key is a secret key. The message
                names the setting, never its value.
        """
        if not production_like:
            return
        for name, value in (
            ("SUPABASE_URL", self.supabase_url),
            ("SUPABASE_PUBLISHABLE_KEY", self.supabase_publishable_key),
        ):
            if _is_unset_or_placeholder(value):
                raise ValueError(f"{name} must be set to the real project value")
        if urlsplit(self.supabase_url).scheme != REQUIRED_URL_SCHEME:
            raise ValueError(f"SUPABASE_URL must use {REQUIRED_URL_SCHEME}")
        if self.supabase_publishable_key.startswith(SECRET_KEY_PREFIX):
            raise ValueError("SUPABASE_PUBLISHABLE_KEY must not be a secret key")
