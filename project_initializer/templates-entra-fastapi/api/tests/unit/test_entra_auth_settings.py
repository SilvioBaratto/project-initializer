"""Unit tests of the Entra authentication settings."""

import pytest
from pydantic import ValidationError

from app.infrastructure.auth_settings import (
    DEFAULT_API_SCOPE,
    DEFAULT_AUTHORITY,
    DEFAULT_JWKS_REFRESH_COOLDOWN_SECONDS,
    DEFAULT_JWKS_TIMEOUT_SECONDS,
    MAX_JWKS_REFRESH_COOLDOWN_SECONDS,
    MAX_JWKS_TIMEOUT_SECONDS,
    PLACEHOLDER_IDENTIFIERS,
    AuthSettings,
    normalize_scope,
)
from app.infrastructure.settings import Settings
from tests.auth_test_env import AUTH_TEST_ENV

pytestmark = pytest.mark.unit

TENANT_ID = "4b1f2d3c-8a6e-4f70-9c25-6e0d7a1b3f84"
CLIENT_ID = "9d2c7e41-5b3a-4c68-a1f0-3e8b6d5a2c97"
SOVEREIGN_AUTHORITY = "https://login.microsoftonline.us"
API_URI = f"api://{CLIENT_ID}"
DEPLOYED_ENVIRONMENTS = ["staging", "production"]
LOCAL_ENVIRONMENTS = ["development", "test"]


@pytest.fixture(autouse=True)
def unset_entra_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide every Entra variable, so defaults are what is tested.

    ``conftest.py`` sets the test tenant and a developer's shell may export any
    other setting; both would otherwise leak into the defaults asserted here.
    """
    setting_names = {field.upper() for field in AuthSettings.model_fields}
    for name in {*AUTH_TEST_ENV, *setting_names}:
        monkeypatch.delenv(name, raising=False)


def settings_for(environment: str, *, tenant: str, client: str) -> Settings:
    """Build the application settings for one stage and one app registration."""
    # A deployed stage refuses a database that is not TLS-protected, which is not
    # what these tests examine.
    return Settings(
        environment=environment,
        entra_tenant_id=tenant,
        entra_api_client_id=client,
        database_ssl_mode="require",
    )


def test_when_nothing_is_configured_then_the_defaults_are_safe():
    """when no Entra variable is set, the scope, authority and timeout have defaults.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    auth_settings = AuthSettings()

    assert auth_settings.entra_api_scope == DEFAULT_API_SCOPE
    assert auth_settings.entra_authority == DEFAULT_AUTHORITY
    assert auth_settings.entra_jwks_timeout == DEFAULT_JWKS_TIMEOUT_SECONDS
    assert auth_settings.entra_jwks_refresh_cooldown == (
        DEFAULT_JWKS_REFRESH_COOLDOWN_SECONDS
    )


def test_when_the_tenant_is_set_then_the_issuer_and_key_url_follow_it():
    """when a tenant id is configured, the v2 issuer and JWKS URL are derived from it.

    Validates app.infrastructure.auth_settings.AuthSettings.entra_issuer.
    """
    auth_settings = AuthSettings(entra_tenant_id=TENANT_ID)

    assert auth_settings.entra_issuer == f"{DEFAULT_AUTHORITY}/{TENANT_ID}/v2.0"
    assert auth_settings.entra_jwks_url == (
        f"{DEFAULT_AUTHORITY}/{TENANT_ID}/discovery/v2.0/keys"
    )


def test_when_a_sovereign_cloud_is_configured_then_it_replaces_the_public_authority():
    """when the authority is a sovereign cloud, the URLs use it, slash trimmed.

    Validates app.infrastructure.auth_settings.AuthSettings.entra_jwks_url.
    """
    auth_settings = AuthSettings(
        entra_tenant_id=TENANT_ID, entra_authority=f"{SOVEREIGN_AUTHORITY}/"
    )

    assert auth_settings.entra_issuer == f"{SOVEREIGN_AUTHORITY}/{TENANT_ID}/v2.0"
    assert auth_settings.entra_jwks_url.startswith(f"{SOVEREIGN_AUTHORITY}/{TENANT_ID}")


@pytest.mark.parametrize(
    "authority",
    ["http://login.microsoftonline.com", "login.microsoftonline.com", ""],
)
def test_when_the_authority_is_not_https_then_it_is_rejected(authority):
    """when the authority is plain HTTP or has no scheme, validation fails.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    with pytest.raises(ValidationError, match="https"):
        AuthSettings(entra_authority=authority)


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        pytest.param("access_as_user", "access_as_user", id="bare-name"),
        pytest.param(f"{API_URI}/access_as_user", "access_as_user", id="api-uri"),
        pytest.param("https://host.example/api/read", "read", id="https-uri"),
        pytest.param("  access_as_user ", "access_as_user", id="padded"),
        pytest.param(f"{API_URI}/", "", id="uri-without-a-scope"),
        pytest.param("", "", id="empty"),
        pytest.param("   ", "", id="blank"),
    ],
)
def test_when_a_scope_is_normalised_then_only_the_bare_name_remains(
    configured, expected
):
    """when a scope is a bare name or a URI, the part after the last slash is kept.

    Validates app.infrastructure.auth_settings.normalize_scope().
    """
    assert normalize_scope(configured) == expected


@pytest.mark.parametrize(
    "scope",
    [
        pytest.param("", id="empty"),
        pytest.param(" ", id="blank"),
        pytest.param("\t", id="tab"),
        pytest.param(f"{API_URI}/", id="uri-without-a-scope"),
        pytest.param(f"{API_URI}/  ", id="uri-with-a-blank-scope"),
        pytest.param("read write", id="two-scopes"),
        pytest.param(f"{API_URI}/read write", id="uri-with-two-scopes"),
    ],
)
def test_when_the_scope_names_nothing_usable_then_validation_fails_not_the_check(
    scope,
):
    """when ENTRA_API_SCOPE is empty or not one scope, settings fail, not the check.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    with pytest.raises(ValidationError, match="ENTRA_API_SCOPE"):
        AuthSettings(entra_api_scope=scope)


@pytest.mark.parametrize("scope", [" access_as_user ", f"{API_URI}/access_as_user"])
def test_when_the_scope_is_padded_or_a_uri_then_the_bare_name_is_stored(scope):
    """when the scope has spaces or a URI prefix, the stored value is its bare name.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    assert AuthSettings(entra_api_scope=scope).entra_api_scope == "access_as_user"


@pytest.mark.parametrize("field", ["entra_tenant_id", "entra_api_client_id"])
@pytest.mark.parametrize(
    ("configured", "stored"),
    [
        pytest.param(TENANT_ID, TENANT_ID, id="canonical"),
        pytest.param(TENANT_ID.upper(), TENANT_ID, id="uppercase-is-lowered"),
        pytest.param(f"  {TENANT_ID}\n", TENANT_ID, id="padding-is-stripped"),
        pytest.param("", "", id="empty-means-unconfigured"),
        pytest.param("   ", "", id="blank-means-unconfigured"),
    ],
)
def test_when_an_identifier_is_a_guid_or_empty_then_it_is_stored_lowercase(
    field, configured, stored
):
    """when a tenant or client id is a GUID in any case, it is stored lowercase.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    assert getattr(AuthSettings(**{field: configured}), field) == stored


@pytest.mark.parametrize("field", ["entra_tenant_id", "entra_api_client_id"])
@pytest.mark.parametrize(
    "configured",
    [
        pytest.param("common", id="common-endpoint"),
        pytest.param("contoso.onmicrosoft.com", id="domain-style-tenant"),
        pytest.param("not-a-guid", id="free-text"),
        pytest.param(f"{{{TENANT_ID}}}", id="braces"),
        pytest.param(f"urn:uuid:{TENANT_ID}", id="urn-prefix"),
        pytest.param(TENANT_ID.replace("-", ""), id="without-hyphens"),
        pytest.param(f"+{TENANT_ID[1:]}", id="sign-in-place-of-a-digit"),
        pytest.param(TENANT_ID[:-1], id="one-digit-short"),
    ],
)
def test_when_an_identifier_is_not_a_guid_then_settings_refuse_to_start(
    field, configured
):
    """when a tenant or client id is no hyphenated GUID, validation names the setting.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    with pytest.raises(ValidationError, match=field.upper()):
        AuthSettings(**{field: configured})


@pytest.mark.parametrize("environment", [*LOCAL_ENVIRONMENTS, *DEPLOYED_ENVIRONMENTS])
def test_when_the_tenant_is_malformed_then_settings_refuse_it_in_every_stage(
    environment,
):
    """when the tenant is not a GUID, the application fails at startup, not per request.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    with pytest.raises(ValidationError, match="ENTRA_TENANT_ID"):
        settings_for(environment, tenant="common", client=CLIENT_ID)


def test_when_the_settings_are_listed_then_only_token_validation_fields_exist():
    """when the fields are listed, only what token validation reads is configurable.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    assert set(AuthSettings.model_fields) == {
        "entra_tenant_id",
        "entra_api_client_id",
        "entra_api_audience",
        "entra_api_scope",
        "entra_authority",
        "entra_jwks_timeout",
        "entra_jwks_refresh_cooldown",
    }


@pytest.mark.parametrize("timeout", [0.1, MAX_JWKS_TIMEOUT_SECONDS])
def test_when_the_key_timeout_is_within_bounds_then_it_is_accepted(timeout):
    """when the JWKS timeout is positive and at most the maximum, it is accepted.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    assert AuthSettings(entra_jwks_timeout=timeout).entra_jwks_timeout == timeout


@pytest.mark.parametrize("timeout", [0, -1, MAX_JWKS_TIMEOUT_SECONDS + 0.1])
def test_when_the_key_timeout_is_out_of_bounds_then_it_is_rejected(timeout):
    """when the JWKS timeout is zero, negative or above the maximum, validation fails.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    with pytest.raises(ValidationError):
        AuthSettings(entra_jwks_timeout=timeout)


@pytest.mark.parametrize("cooldown", [0.1, MAX_JWKS_REFRESH_COOLDOWN_SECONDS])
def test_when_the_refresh_cooldown_is_within_bounds_then_it_is_accepted(cooldown):
    """when the cooldown is positive and at most the maximum, it is accepted.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    settings = AuthSettings(entra_jwks_refresh_cooldown=cooldown)

    assert settings.entra_jwks_refresh_cooldown == cooldown


@pytest.mark.parametrize("cooldown", [0, -1, MAX_JWKS_REFRESH_COOLDOWN_SECONDS + 0.1])
def test_when_the_refresh_cooldown_is_out_of_bounds_then_it_is_rejected(cooldown):
    """when the cooldown is zero, negative or too long, validation fails.

    A zero cooldown would let every unknown key id reload the key set.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    with pytest.raises(ValidationError):
        AuthSettings(entra_jwks_refresh_cooldown=cooldown)


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_when_a_deployed_stage_has_a_real_registration_then_settings_are_accepted(
    environment,
):
    """when staging or production names a real tenant and API client, Settings builds.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    built = settings_for(environment, tenant=TENANT_ID, client=CLIENT_ID)

    assert built.entra_tenant_id == TENANT_ID


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize(
    ("tenant", "client", "named_setting"),
    [
        pytest.param("", CLIENT_ID, "ENTRA_TENANT_ID", id="empty-tenant"),
        pytest.param(
            sorted(PLACEHOLDER_IDENTIFIERS)[0],
            CLIENT_ID,
            "ENTRA_TENANT_ID",
            id="placeholder-tenant",
        ),
        pytest.param(TENANT_ID, "", "ENTRA_API_CLIENT_ID", id="empty-client"),
        pytest.param(
            TENANT_ID,
            sorted(PLACEHOLDER_IDENTIFIERS)[1],
            "ENTRA_API_CLIENT_ID",
            id="placeholder-client",
        ),
    ],
)
def test_when_a_deployed_stage_has_no_real_registration_then_settings_are_refused(
    environment, tenant, client, named_setting
):
    """when a deployed stage lacks a real tenant or client id, Settings fails naming it.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    with pytest.raises(ValidationError, match=named_setting):
        settings_for(environment, tenant=tenant, client=client)


@pytest.mark.parametrize("environment", LOCAL_ENVIRONMENTS)
def test_when_the_stage_is_local_then_an_unconfigured_registration_is_accepted(
    environment,
):
    """when development or test has no Entra values, Settings still builds.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    built = settings_for(environment, tenant="", client="")

    assert (built.entra_tenant_id, built.entra_api_client_id) == ("", "")
