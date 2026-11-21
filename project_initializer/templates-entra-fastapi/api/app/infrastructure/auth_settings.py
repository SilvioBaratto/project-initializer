"""Authentication settings of the Microsoft Entra ID variant.

The API validates Entra v2 access tokens in-process against the tenant's public
signing keys, so it needs the tenant, the API app registration and the scope its
clients must have been granted. No client secret is involved.
"""

from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings

DEFAULT_AUTHORITY = "https://login.microsoftonline.com"
DEFAULT_API_SCOPE = "access_as_user"
DEFAULT_JWKS_TIMEOUT_SECONDS = 5.0
MAX_JWKS_TIMEOUT_SECONDS = 30.0
DEFAULT_JWKS_REFRESH_COOLDOWN_SECONDS = 30.0
MAX_JWKS_REFRESH_COOLDOWN_SECONDS = 3600.0
REQUIRED_AUTHORITY_SCHEME = "https://"
SCOPE_SEPARATOR = "/"

# The identifiers the generated ``.env`` ships so a fresh scaffold is readable.
PLACEHOLDER_IDENTIFIERS = frozenset(
    {
        "00000000-0000-0000-0000-000000000000",
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    }
)


def normalize_scope(scope: str) -> str:
    """Reduce a scope to the bare name that the ``scp`` claim carries.

    Args:
        scope: A bare name such as ``access_as_user`` or a full URI such as
            ``api://<client id>/access_as_user``.

    Returns:
        The part after the last ``/``, trimmed; empty when none is left.
    """
    return scope.rsplit(SCOPE_SEPARATOR, 1)[-1].strip()


def _require_scope_name(scope: str) -> str:
    # ``scp`` is a space-separated list, so a name with a space inside could never
    # match and would lock every caller out.
    name = normalize_scope(scope)
    if len(name.split()) != 1:
        raise ValueError(
            "ENTRA_API_SCOPE must be one scope name or a URI that ends in one"
        )
    return name


# Validated after the URI prefix is dropped, so ``api://<id>/`` is refused instead
# of reaching the verifier as an empty requirement.
ScopeName = Annotated[str, AfterValidator(_require_scope_name)]


class AuthSettings(BaseSettings):
    """Entra configuration shared into ``Settings``.

    Attributes:
        entra_tenant_id: Directory (tenant) id that issues the tokens, as a GUID
            or empty. It is stored lowercase, the way the ``tid`` claim is
            written, so the issuer and the tenant check compare equal.
        entra_api_client_id: Application (client) id of the API registration, as
            a GUID or empty. Stored lowercase.
        entra_api_audience: Extra audience to accept besides the client id and
            ``api://<client id>``; leave empty when the registration issues one
            of those two.
        entra_api_scope: Delegated scope a caller must hold, stored as its bare
            name. Both the bare name (``access_as_user``) and the full URI that
            MSAL requests (``api://<client id>/access_as_user``) are accepted.
            It can never be empty, so the scope check cannot be switched off by
            omission.
        entra_authority: Base URL of the identity platform. Change it for a
            sovereign cloud, such as ``https://login.microsoftonline.us``.
        entra_jwks_timeout: Seconds to wait for the tenant's signing keys. It
            bounds how long one request can occupy a worker thread.
        entra_jwks_refresh_cooldown: Minimum seconds between two forced reloads
            of the key set. A token naming a key the cache lacks triggers a
            reload, and anybody can send such a token, so this bounds the
            requests the API makes to Entra on a stranger's behalf. A key that
            Entra has just rotated in is picked up after at most this long.
    """

    entra_tenant_id: str = ""
    entra_api_client_id: str = ""
    entra_api_audience: str = ""
    entra_api_scope: ScopeName = DEFAULT_API_SCOPE
    entra_authority: str = DEFAULT_AUTHORITY
    entra_jwks_timeout: float = Field(
        default=DEFAULT_JWKS_TIMEOUT_SECONDS, gt=0, le=MAX_JWKS_TIMEOUT_SECONDS
    )
    entra_jwks_refresh_cooldown: float = Field(
        default=DEFAULT_JWKS_REFRESH_COOLDOWN_SECONDS,
        gt=0,
        le=MAX_JWKS_REFRESH_COOLDOWN_SECONDS,
    )

    @field_validator("entra_tenant_id", "entra_api_client_id")
    @classmethod
    def _identifier_must_be_a_guid(cls, value: str, info: ValidationInfo) -> str:
        # A domain-style or ``common`` tenant never equals the ``tid`` claim, so
        # every token would be refused; failing at startup beats that.
        name = str(info.field_name).upper()
        candidate = value.strip()
        if not candidate:
            return ""
        try:
            parsed = UUID(candidate)
        except ValueError:
            raise ValueError(f"{name} must be a GUID") from None
        # The parser also accepts braces, a urn prefix and a form without hyphens,
        # but only the portal's own spelling is a value this API can compare.
        if str(parsed) != candidate.lower():
            raise ValueError(f"{name} must be a GUID written with hyphens")
        return str(parsed)

    @field_validator("entra_authority")
    @classmethod
    def _authority_must_be_https(cls, value: str) -> str:
        # The signing keys are fetched from here; over plain HTTP anybody on the
        # path could substitute their own key and mint accepted tokens.
        if not value.startswith(REQUIRED_AUTHORITY_SCHEME):
            raise ValueError("ENTRA_AUTHORITY must be an https URL")
        return value.rstrip("/")

    @property
    def entra_jwks_url(self) -> str:
        """Endpoint that publishes the tenant's token signing keys."""
        return f"{self.entra_authority}/{self.entra_tenant_id}/discovery/v2.0/keys"

    @property
    def entra_issuer(self) -> str:
        """Value of the ``iss`` claim in this tenant's v2 access tokens."""
        return f"{self.entra_authority}/{self.entra_tenant_id}/v2.0"

    def validate_auth_secrets(self, *, production_like: bool) -> None:
        """Reject a missing or placeholder tenant or API registration when deployed.

        Args:
            production_like: True for the staging and production environments.
                Development and test accept any value, so a fresh scaffold runs
                before the app registration exists.

        Raises:
            ValueError: The tenant id or the API client id is empty or one of
                the placeholder ids. The message names the setting, never its
                value.
        """
        if not production_like:
            return
        for name, value in (
            ("ENTRA_TENANT_ID", self.entra_tenant_id),
            ("ENTRA_API_CLIENT_ID", self.entra_api_client_id),
        ):
            if not value or value in PLACEHOLDER_IDENTIFIERS:
                raise ValueError(f"{name} must be set to the real registration value")
