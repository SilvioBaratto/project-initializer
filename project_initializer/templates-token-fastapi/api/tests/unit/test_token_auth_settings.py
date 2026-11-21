"""Unit tests for the authentication settings of the token variant."""

import pytest
from pydantic import ValidationError

from app.infrastructure.auth_settings import (
    DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
    MAX_ACCESS_TOKEN_EXPIRE_MINUTES,
    MIN_ACCESS_TOKEN_EXPIRE_MINUTES,
    MIN_JWT_SECRET_LENGTH,
    MIN_STATIC_TOKEN_LENGTH,
    PLACEHOLDER_SECRETS,
    AuthSettings,
)
from app.infrastructure.settings import Settings

pytestmark = pytest.mark.unit

STRONG_TOKEN = "t" * MIN_STATIC_TOKEN_LENGTH
STRONG_JWT_SECRET = "j" * MIN_JWT_SECRET_LENGTH
WEAK_TOKEN = "weaktok"
CUSTOM_LIFETIME_MINUTES = 60
PRODUCTION_LIKE_ENVIRONMENTS = ["staging", "production"]
LOCAL_ENVIRONMENTS = ["development", "test"]
WEAK_NON_EMPTY_SECRETS = [
    pytest.param("changeme", id="placeholder"),
    pytest.param("  ChangeMe  ", id="placeholder-with-case-and-spaces"),
    pytest.param("SECRET", id="placeholder-upper-case"),
    pytest.param("short", id="short"),
]
UNACCEPTABLE_SECRETS = [pytest.param("", id="empty"), *WEAK_NON_EMPTY_SECRETS]


@pytest.fixture(autouse=True)
def clean_auth_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide the test environment so each case states every setting it relies on."""
    for name in (
        "AUTH_TOKEN",
        "JWT_SECRET_KEY",
        "JWT_ALGORITHM",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
    ):
        monkeypatch.delenv(name, raising=False)


def build_settings(
    environment: str, *, auth_token: str = STRONG_TOKEN, jwt_secret: str
) -> Settings:
    """Build full application settings for a stage with the given secrets."""
    # A deployed stage refuses a database that is not TLS-protected, which is not
    # what these tests examine.
    return Settings(
        environment=environment,
        auth_token=auth_token,
        jwt_secret_key=jwt_secret,
        database_ssl_mode="require",
    )


def test_when_nothing_is_configured_then_the_secrets_are_empty_and_the_defaults_apply():
    """when no variable is set, both secrets are empty and the token policy is default.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    auth_settings = AuthSettings()

    assert auth_settings.auth_token.get_secret_value() == ""
    assert auth_settings.jwt_secret_key.get_secret_value() == ""
    assert auth_settings.jwt_algorithm == "HS256"
    assert (
        auth_settings.access_token_expire_minutes == DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES
    )


def test_when_the_environment_sets_the_values_then_they_are_read(
    monkeypatch: pytest.MonkeyPatch,
):
    """when the variables are set, the settings take them, case-insensitively.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    monkeypatch.setenv("AUTH_TOKEN", STRONG_TOKEN)
    monkeypatch.setenv("jwt_secret_key", STRONG_JWT_SECRET)
    monkeypatch.setenv("JWT_ALGORITHM", "HS512")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(CUSTOM_LIFETIME_MINUTES))

    auth_settings = AuthSettings()

    assert auth_settings.auth_token.get_secret_value() == STRONG_TOKEN
    assert auth_settings.jwt_secret_key.get_secret_value() == STRONG_JWT_SECRET
    assert auth_settings.jwt_algorithm == "HS512"
    assert auth_settings.access_token_expire_minutes == CUSTOM_LIFETIME_MINUTES


def test_when_the_settings_are_printed_then_the_secrets_are_masked():
    """when the settings are rendered as text, neither secret value appears.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    auth_settings = AuthSettings(
        auth_token=STRONG_TOKEN, jwt_secret_key=STRONG_JWT_SECRET
    )

    rendered = f"{auth_settings!r} {auth_settings}"

    assert STRONG_TOKEN not in rendered
    assert STRONG_JWT_SECRET not in rendered


@pytest.mark.parametrize("algorithm", ["HS256", "HS384", "HS512"])
def test_when_an_hmac_algorithm_is_configured_then_it_is_accepted(algorithm):
    """when the algorithm is one of the three HMAC variants, it is accepted.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    assert AuthSettings(jwt_algorithm=algorithm).jwt_algorithm == algorithm


@pytest.mark.parametrize("algorithm", ["none", "RS256", "ES256", "hs256", ""])
def test_when_another_algorithm_is_configured_then_it_is_rejected(algorithm):
    """when the algorithm is none, asymmetric or misspelled, validation fails.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    with pytest.raises(ValidationError):
        AuthSettings(jwt_algorithm=algorithm)


@pytest.mark.parametrize(
    "minutes", [MIN_ACCESS_TOKEN_EXPIRE_MINUTES, MAX_ACCESS_TOKEN_EXPIRE_MINUTES]
)
def test_when_the_lifetime_is_on_a_bound_then_it_is_accepted(minutes):
    """when the lifetime is one minute or one day, it is accepted.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    assert AuthSettings(
        access_token_expire_minutes=minutes
    ).access_token_expire_minutes == (minutes)


@pytest.mark.parametrize(
    "minutes", [0, -1, MAX_ACCESS_TOKEN_EXPIRE_MINUTES + 1, 10_000_000]
)
def test_when_the_lifetime_is_outside_the_bounds_then_it_is_rejected(minutes):
    """when the lifetime is below one minute or above one day, validation fails.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    with pytest.raises(ValidationError):
        AuthSettings(access_token_expire_minutes=minutes)


@pytest.mark.parametrize("environment", PRODUCTION_LIKE_ENVIRONMENTS)
def test_when_both_secrets_are_strong_then_a_production_like_stage_starts(environment):
    """when the secrets meet their minimums, staging and production accept them.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    accepted = build_settings(environment, jwt_secret=STRONG_JWT_SECRET)

    assert accepted.auth_token.get_secret_value() == STRONG_TOKEN
    assert accepted.jwt_secret_key.get_secret_value() == STRONG_JWT_SECRET


@pytest.mark.parametrize("environment", PRODUCTION_LIKE_ENVIRONMENTS)
@pytest.mark.parametrize("auth_token", UNACCEPTABLE_SECRETS)
def test_when_the_static_token_is_weak_then_a_production_like_stage_refuses_to_start(
    environment, auth_token
):
    """when AUTH_TOKEN is weak, staging and production refuse to start.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    with pytest.raises(ValidationError, match="AUTH_TOKEN") as raised:
        build_settings(environment, auth_token=auth_token, jwt_secret=STRONG_JWT_SECRET)

    assert STRONG_JWT_SECRET not in str(raised.value)


@pytest.mark.parametrize("environment", PRODUCTION_LIKE_ENVIRONMENTS)
def test_when_a_secret_is_rejected_then_the_error_does_not_echo_it(environment):
    """when a weak secret stops startup, the validation error does not print its value.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    with pytest.raises(ValidationError) as raised:
        build_settings(environment, auth_token=WEAK_TOKEN, jwt_secret=STRONG_JWT_SECRET)

    assert WEAK_TOKEN not in str(raised.value)
    assert STRONG_JWT_SECRET not in str(raised.value)


@pytest.mark.parametrize("environment", PRODUCTION_LIKE_ENVIRONMENTS)
@pytest.mark.parametrize("jwt_secret", UNACCEPTABLE_SECRETS)
def test_when_the_jwt_secret_is_weak_then_a_production_like_stage_refuses_to_start(
    environment, jwt_secret
):
    """when JWT_SECRET_KEY is weak, staging and production refuse to start.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY") as raised:
        build_settings(environment, jwt_secret=jwt_secret)

    assert STRONG_TOKEN not in str(raised.value)


@pytest.mark.parametrize("environment", PRODUCTION_LIKE_ENVIRONMENTS)
def test_when_a_secret_is_one_character_short_then_it_is_refused(environment):
    """when a secret is one character under its minimum, the boundary is rejected.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    with pytest.raises(ValidationError, match="AUTH_TOKEN"):
        build_settings(
            environment,
            auth_token="t" * (MIN_STATIC_TOKEN_LENGTH - 1),
            jwt_secret=STRONG_JWT_SECRET,
        )
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        build_settings(environment, jwt_secret="j" * (MIN_JWT_SECRET_LENGTH - 1))


@pytest.mark.parametrize("environment", LOCAL_ENVIRONMENTS)
def test_when_the_stage_is_local_then_empty_secrets_are_allowed(environment):
    """when the stage is development or test, empty secrets start with the features off.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    accepted = build_settings(environment, auth_token="", jwt_secret="")

    assert accepted.auth_token.get_secret_value() == ""
    assert accepted.jwt_secret_key.get_secret_value() == ""


@pytest.mark.parametrize("environment", LOCAL_ENVIRONMENTS)
@pytest.mark.parametrize("secret", WEAK_NON_EMPTY_SECRETS)
def test_when_the_stage_is_local_then_a_weak_static_token_is_still_refused(
    environment, secret
):
    """when AUTH_TOKEN is set but weak, even development refuses to start.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    with pytest.raises(ValidationError, match="AUTH_TOKEN"):
        build_settings(environment, auth_token=secret, jwt_secret="")


@pytest.mark.parametrize("environment", LOCAL_ENVIRONMENTS)
@pytest.mark.parametrize("secret", WEAK_NON_EMPTY_SECRETS)
def test_when_the_stage_is_local_then_a_weak_jwt_secret_is_still_refused(
    environment, secret
):
    """when JWT_SECRET_KEY is set but weak, even development refuses to start.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        build_settings(environment, auth_token="", jwt_secret=secret)


def test_when_placeholders_are_listed_then_they_are_lower_case():
    """when the placeholder set is read, every entry is lower case.

    The comparison lower-cases the candidate, so an upper-case entry would
    never match.

    Validates app.infrastructure.auth_settings.PLACEHOLDER_SECRETS.
    """
    assert all(entry == entry.lower() for entry in PLACEHOLDER_SECRETS)
