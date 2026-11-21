"""Authentication settings seam.

``Settings`` inherits from ``AuthSettings`` so each auth variant can add its own
configuration fields without touching ``settings.py``. This module is the only
settings file an auth overlay replaces.
"""

from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    """Authentication-specific configuration shared into ``Settings``.

    The base variant has no authentication, so it declares no fields. Overlays
    replace this module with a class of the same name that adds their fields and
    overrides ``validate_auth_secrets``.
    """

    def validate_auth_secrets(self, *, production_like: bool) -> None:
        """Reject credentials that must not run in a production-like deployment.

        Called by ``Settings`` once every field has been validated.

        Args:
            production_like: True for the staging and production environments,
                where placeholder or weak secrets are unacceptable.

        Raises:
            ValueError: A secret is missing, a placeholder, or too weak. The
                message names the setting, never its value.
        """
