"""Unit tests for the application settings."""

import os
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import ValidationError

from app.infrastructure.settings import DEFAULT_DATABASE_URL, Settings

pytestmark = pytest.mark.unit

API_ROOT = Path(__file__).resolve().parents[2]

DEPLOYED_ENVIRONMENTS = ["staging", "production"]
LOCAL_ENVIRONMENTS = ["development", "test"]
ENCRYPTED_SSL_MODES = ["require", "verify-ca", "verify-full"]
UNENCRYPTED_SSL_MODES = ["disable", "allow", "prefer"]
DATABASE_PASSWORD = "s3cr3t-pw"
DATABASE_USER = "svc_user"
DATABASE_HOST = "db.internal.example"
CREDENTIALED_URL = (
    f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:5432/app"
)
INSECURE_TRANSPORT_OPT_OUT = "DATABASE_ALLOW_INSECURE_TRANSPORT"

# Field -> (lowest accepted, highest accepted). Each bound is asserted from both
# sides, so a loosened or tightened limit fails a test.
INTEGER_BOUNDS = {
    "database_pool_size": (1, 100),
    "database_max_overflow": (0, 100),
    "database_pool_timeout": (1, 300),
    "database_pool_recycle": (30, 86400),
    "database_connect_timeout": (1, 120),
    "database_breaker_failure_threshold": (1, 100),
    "rate_limit_requests": (1, 100_000),
    "rate_limit_window": (1, 3600),
}


class _SecretsAcceptingSettings(Settings):
    def validate_auth_secrets(self, *, production_like: bool) -> None:
        """Accept every secret, whatever the installed auth variant demands."""


@pytest.fixture(autouse=True)
def empty_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide the developer's environment so each test controls every input."""
    for name in list(os.environ):
        monkeypatch.delenv(name)


def test_when_the_environment_is_empty_then_settings_use_development() -> None:
    """Validates app.infrastructure.settings.Settings.

    A bare environment must yield a usable development configuration, because
    tools import the module before any ``.env`` exists.
    """
    settings = Settings()

    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.database_url == DEFAULT_DATABASE_URL


def test_when_the_default_database_url_is_used_then_it_carries_no_credentials() -> None:
    """Validates app.infrastructure.settings.DEFAULT_DATABASE_URL."""
    assert "@" not in DEFAULT_DATABASE_URL


def test_when_no_variable_is_set_then_importing_the_module_succeeds() -> None:
    """Validates app.infrastructure.settings.settings.

    The module-level singleton is built at import time; a fresh interpreter with
    no variables proves it needs none.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import app.infrastructure.settings"],
        env={"PYTHONPATH": str(API_ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("environment", ["test", "staging", "production"])
def test_when_debug_is_set_outside_development_then_settings_are_refused(
    environment: str,
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    with pytest.raises(ValidationError, match="DEBUG"):
        Settings(environment=environment, debug=True)


def test_when_debug_is_set_in_development_then_it_is_accepted() -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    assert Settings(environment="development", debug=True).debug is True


@pytest.mark.parametrize("environment", ["test", "staging", "production"])
def test_when_sql_echo_is_set_outside_development_then_settings_are_refused(
    environment: str,
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    with pytest.raises(ValidationError, match="DATABASE_ECHO"):
        Settings(environment=environment, database_echo=True)


def test_when_sql_echo_is_set_in_development_then_it_is_accepted() -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    assert Settings(environment="development", database_echo=True).database_echo


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("origins", ["*", "http://a.test, *", "*,http://a.test"])
def test_when_cors_allows_all_origins_when_deployed_then_settings_are_refused(
    environment: str, origins: str
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(environment=environment, cors_origins=origins)


@pytest.mark.parametrize("environment", ["development", "test"])
def test_when_cors_allows_all_origins_locally_then_it_is_accepted(
    environment: str,
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    assert Settings(environment=environment, cors_origins="*").cors_origins_list == [
        "*"
    ]


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_when_cors_lists_explicit_origins_when_deployed_then_it_is_accepted(
    environment: str,
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy().

    Uses a variant-neutral subclass so the auth secrets a variant demands in a
    deployed stage do not decide the outcome.
    """
    settings = _SecretsAcceptingSettings(
        environment=environment,
        cors_origins="https://app.example.com",
        database_ssl_mode="require",
    )

    assert settings.cors_origins_list == ["https://app.example.com"]


def test_when_a_value_is_rejected_then_the_error_does_not_echo_it() -> None:
    """Validates app.infrastructure.settings.Settings.model_config."""
    leaked_value = "not-a-number-s3cr3t"

    with pytest.raises(ValidationError) as raised:
        Settings(rate_limit_window=leaked_value)

    assert leaked_value not in str(raised.value)


def test_when_debug_comes_from_the_environment_then_the_policy_applies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates app.infrastructure.settings.Settings.debug."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")

    with pytest.raises(ValidationError, match="DEBUG"):
        Settings()


def test_when_the_environment_name_is_unknown_then_settings_are_refused() -> None:
    """Validates app.infrastructure.settings.Environment."""
    with pytest.raises(ValidationError):
        Settings(environment="prod")


@pytest.mark.parametrize("raw_level", ["warning", "WARNING", "Warning"])
def test_when_the_log_level_has_any_letter_case_then_it_is_lowercased(
    monkeypatch: pytest.MonkeyPatch, raw_level: str
) -> None:
    """Validates app.infrastructure.settings.LogLevel."""
    monkeypatch.setenv("LOG_LEVEL", raw_level)

    assert Settings().log_level == "warning"


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("log_level", "verbose"),
        ("log_format", "xml"),
        ("database_ssl_mode", "sometimes"),
    ],
)
def test_when_an_enumerated_setting_is_unknown_then_settings_are_refused(
    field: str, invalid_value: str
) -> None:
    """Validates app.infrastructure.settings.Settings."""
    with pytest.raises(ValidationError):
        Settings(**{field: invalid_value})


@pytest.mark.parametrize("ssl_mode", ["disable", "require", "verify-full"])
def test_when_the_ssl_mode_is_a_libpq_mode_then_it_is_accepted(ssl_mode: str) -> None:
    """Validates app.infrastructure.settings.SslMode."""
    assert Settings(database_ssl_mode=ssl_mode).database_ssl_mode == ssl_mode


@pytest.mark.parametrize(("field", "bounds"), INTEGER_BOUNDS.items())
def test_when_an_integer_setting_hits_its_bounds_then_only_values_beyond_are_refused(
    field: str, bounds: tuple[int, int]
) -> None:
    """Validates app.infrastructure.settings.Settings."""
    lowest, highest = bounds

    assert getattr(Settings(**{field: lowest}), field) == lowest
    assert getattr(Settings(**{field: highest}), field) == highest
    with pytest.raises(ValidationError):
        Settings(**{field: lowest - 1})
    with pytest.raises(ValidationError):
        Settings(**{field: highest + 1})


@pytest.mark.parametrize("reset_timeout", [0.0, -1.0, 600.5])
def test_when_the_reset_timeout_is_out_of_range_then_it_is_refused(
    reset_timeout: float,
) -> None:
    """Validates app.infrastructure.settings.Settings.database_breaker_reset_timeout."""
    with pytest.raises(ValidationError):
        Settings(database_breaker_reset_timeout=reset_timeout)


@pytest.mark.parametrize("reset_timeout", [0.1, 600.0])
def test_when_the_reset_timeout_is_in_range_then_it_is_accepted(
    reset_timeout: float,
) -> None:
    """Validates app.infrastructure.settings.Settings.database_breaker_reset_timeout."""
    settings = Settings(database_breaker_reset_timeout=reset_timeout)

    assert settings.database_breaker_reset_timeout == reset_timeout


@pytest.mark.parametrize(
    ("environment", "is_production", "is_staging", "is_production_like", "is_local"),
    [
        ("development", False, False, False, True),
        ("test", False, False, False, True),
        ("staging", False, True, True, False),
        ("production", True, False, True, False),
    ],
)
def test_when_the_environment_is_set_then_the_stage_flags_follow(
    environment: str,
    is_production: bool,
    is_staging: bool,
    is_production_like: bool,
    is_local: bool,
) -> None:
    """Validates app.infrastructure.settings.Settings.is_production_like.

    Built without validation so the test does not depend on which auth variant
    is installed and what secrets its production-like stages demand.
    """
    settings = Settings.model_construct(environment=environment)

    assert settings.is_production is is_production
    assert settings.is_staging is is_staging
    assert settings.is_production_like is is_production_like
    assert settings.is_local is is_local


@pytest.mark.parametrize(
    ("environment", "expected"),
    [("development", True), ("test", False), ("staging", False), ("production", False)],
)
def test_when_debug_is_set_then_is_development_still_follows_the_environment(
    environment: str, expected: bool
) -> None:
    """Validates app.infrastructure.settings.Settings.is_development."""
    settings = Settings.model_construct(environment=environment, debug=True)

    assert settings.is_development is expected


@pytest.mark.parametrize(
    ("environment", "api_docs_enabled", "expected"),
    [
        ("development", None, True),
        ("test", None, True),
        ("staging", None, True),
        ("production", None, False),
        ("production", True, True),
        ("development", False, False),
    ],
)
def test_when_the_docs_switch_is_unset_then_the_docs_follow_the_environment(
    environment: str, api_docs_enabled: bool | None, expected: bool
) -> None:
    """Validates app.infrastructure.settings.Settings.docs_enabled."""
    settings = Settings.model_construct(
        environment=environment, api_docs_enabled=api_docs_enabled
    )

    assert settings.docs_enabled is expected


@pytest.mark.parametrize(
    ("raw_origins", "expected"),
    [
        ("http://a.test", ["http://a.test"]),
        (" http://a.test , http://b.test ", ["http://a.test", "http://b.test"]),
        ("http://a.test,,http://b.test,", ["http://a.test", "http://b.test"]),
        ("", []),
        (" , ", []),
    ],
)
def test_when_cors_origins_are_listed_then_they_are_split_and_trimmed(
    raw_origins: str, expected: list[str]
) -> None:
    """Validates app.infrastructure.settings.Settings.cors_origins_list."""
    assert Settings(cors_origins=raw_origins).cors_origins_list == expected


def test_when_database_url_is_set_then_it_is_read_from_its_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates app.infrastructure.settings.Settings.database_url."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://db.test/app")

    assert Settings().database_url == "postgresql://db.test/app"


def test_when_no_direct_url_is_set_then_migrations_use_the_runtime_url() -> None:
    """Validates app.infrastructure.settings.Settings.migration_database_url."""
    settings = Settings(database_url="postgresql://pooled.test/app")

    assert settings.migration_database_url == "postgresql://pooled.test/app"


def test_when_a_direct_url_is_set_then_migrations_prefer_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates app.infrastructure.settings.Settings.migration_database_url."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://pooled.test/app")
    monkeypatch.setenv("DIRECT_DATABASE_URL", "postgresql://direct.test/app")

    assert Settings().migration_database_url == "postgresql://direct.test/app"


def test_when_an_unrelated_variable_is_set_then_it_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates app.infrastructure.settings.Settings.model_config."""
    monkeypatch.setenv("SOMETHING_ELSE_ENTIRELY", "x")

    assert Settings().environment == "development"


class _RecordingSettings(Settings):
    stages_seen: ClassVar[list[bool]] = []

    def validate_auth_secrets(self, *, production_like: bool) -> None:
        """Record the stage instead of validating anything."""
        self.stages_seen.append(production_like)


class _RejectingSettings(Settings):
    def validate_auth_secrets(self, *, production_like: bool) -> None:
        """Always reject, as an overlay does for a placeholder secret."""
        raise ValueError("AUTH_SECRET is a placeholder")


@pytest.mark.parametrize(
    ("environment", "production_like"),
    [("development", False), ("test", False), ("staging", True), ("production", True)],
)
def test_when_settings_validate_then_auth_secrets_learn_the_stage(
    environment: str, production_like: bool
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    _RecordingSettings.stages_seen.clear()

    _RecordingSettings(environment=environment, database_ssl_mode="require")

    assert _RecordingSettings.stages_seen == [production_like]


def test_when_auth_secrets_are_rejected_then_settings_validation_fails() -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    with pytest.raises(ValidationError, match="AUTH_SECRET"):
        _RejectingSettings()


def _deployed_settings(environment: str, **overrides: object) -> Settings:
    """Build settings of a deployed stage that reach a credentialed database.

    Uses a variant-neutral subclass so the auth secrets a variant demands in a
    deployed stage do not decide the outcome.
    """
    values: dict[str, object] = {"database_url": CREDENTIALED_URL}
    return _SecretsAcceptingSettings(environment=environment, **(values | overrides))


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("ssl_mode", [None, *UNENCRYPTED_SSL_MODES])
def test_when_the_database_is_not_tls_protected_when_deployed_then_settings_are_refused(
    environment: str, ssl_mode: str | None
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    with pytest.raises(ValidationError, match="DATABASE_SSL_MODE"):
        _deployed_settings(environment, database_ssl_mode=ssl_mode)


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("ssl_mode", ENCRYPTED_SSL_MODES)
def test_when_the_ssl_mode_encrypts_when_deployed_then_settings_are_accepted(
    environment: str, ssl_mode: str
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    built = _deployed_settings(environment, database_ssl_mode=ssl_mode)

    assert built.database_ssl_mode == ssl_mode


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("ssl_mode", ENCRYPTED_SSL_MODES)
def test_when_the_url_carries_an_encrypting_sslmode_then_settings_are_accepted(
    environment: str, ssl_mode: str
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    built = _deployed_settings(
        environment, database_url=f"{CREDENTIALED_URL}?sslmode={ssl_mode}"
    )

    assert built.database_ssl_mode is None


@pytest.mark.parametrize("ssl_mode", UNENCRYPTED_SSL_MODES)
def test_when_the_url_carries_a_clear_text_sslmode_then_settings_are_refused(
    ssl_mode: str,
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    with pytest.raises(ValidationError, match="DATABASE_SSL_MODE"):
        _deployed_settings(
            "production", database_url=f"{CREDENTIALED_URL}?sslmode={ssl_mode}"
        )


def test_when_the_url_repeats_sslmode_then_settings_are_refused() -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy().

    A repeated parameter is ambiguous, so it cannot vouch for the connection.
    """
    with pytest.raises(ValidationError, match="DATABASE_SSL_MODE"):
        _deployed_settings(
            "production",
            database_url=f"{CREDENTIALED_URL}?sslmode=require&sslmode=require",
        )


def test_when_the_configured_mode_is_clear_text_then_it_overrides_an_encrypting_url() -> (
    None
):
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy().

    The connection is opened with the configured mode, so that is the one judged.
    """
    with pytest.raises(ValidationError, match="DATABASE_SSL_MODE"):
        _deployed_settings(
            "production",
            database_url=f"{CREDENTIALED_URL}?sslmode=require",
            database_ssl_mode="disable",
        )


def test_when_the_configured_mode_encrypts_then_it_overrides_a_clear_text_url() -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    built = _deployed_settings(
        "production",
        database_url=f"{CREDENTIALED_URL}?sslmode=disable",
        database_ssl_mode="require",
    )

    assert built.database_ssl_mode == "require"


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_when_insecure_transport_is_allowed_then_a_clear_text_database_is_accepted(
    environment: str,
) -> None:
    """Validates app.infrastructure.settings.Settings.database_allow_insecure_transport."""
    built = _deployed_settings(environment, database_allow_insecure_transport=True)

    assert built.database_ssl_mode is None


def test_when_the_opt_out_comes_from_the_environment_then_it_is_honoured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates app.infrastructure.settings.Settings.database_allow_insecure_transport."""
    monkeypatch.setenv(INSECURE_TRANSPORT_OPT_OUT, "true")

    built = _deployed_settings("production")

    assert built.database_allow_insecure_transport is True


def test_when_the_opt_out_is_unset_then_it_defaults_to_refusing() -> None:
    """Validates app.infrastructure.settings.Settings.database_allow_insecure_transport."""
    assert Settings().database_allow_insecure_transport is False


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("sqlite_url", ["sqlite://", "sqlite:///./local.db"])
def test_when_the_database_is_sqlite_then_the_tls_requirement_does_not_apply(
    environment: str, sqlite_url: str
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    built = _deployed_settings(environment, database_url=sqlite_url)

    assert built.database_url == sqlite_url


@pytest.mark.parametrize("environment", LOCAL_ENVIRONMENTS)
@pytest.mark.parametrize("ssl_mode", [None, *UNENCRYPTED_SSL_MODES])
def test_when_the_stage_is_local_then_a_clear_text_database_is_accepted(
    environment: str, ssl_mode: str | None
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    built = _deployed_settings(environment, database_ssl_mode=ssl_mode)

    assert built.database_ssl_mode == ssl_mode


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_when_the_tls_requirement_refuses_the_url_then_the_error_names_settings_only(
    environment: str,
) -> None:
    """Validates app.infrastructure.settings.INSECURE_TRANSPORT_MESSAGE.

    The error must name the setting to change and the opt-out, and must not
    carry any part of the URL, because the URL holds credentials.
    """
    with pytest.raises(ValidationError) as raised:
        _deployed_settings(environment)

    message = str(raised.value)
    assert "DATABASE_URL" in message
    assert "DATABASE_SSL_MODE" in message
    assert INSECURE_TRANSPORT_OPT_OUT in message
    for secret_part in (DATABASE_PASSWORD, DATABASE_USER, DATABASE_HOST):
        assert secret_part not in message


def test_when_the_migration_url_is_clear_text_then_settings_name_it_and_are_refused() -> (
    None
):
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy().

    Migrations connect over the network too, so their URL needs the same TLS.
    """
    with pytest.raises(ValidationError, match="DIRECT_DATABASE_URL") as raised:
        _deployed_settings(
            "production",
            database_url=f"{CREDENTIALED_URL}?sslmode=require",
            database_migration_url=CREDENTIALED_URL,
        )

    assert DATABASE_PASSWORD not in str(raised.value)


def test_when_the_configured_mode_encrypts_then_the_migration_url_is_accepted() -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    built = _deployed_settings(
        "production",
        database_ssl_mode="require",
        database_migration_url=CREDENTIALED_URL,
    )

    assert built.migration_database_url == CREDENTIALED_URL


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_when_the_database_url_cannot_be_parsed_then_the_error_does_not_echo_it(
    environment: str,
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    unparsable = f"not-a-url-{DATABASE_PASSWORD}"

    with pytest.raises(ValidationError, match="DATABASE_URL") as raised:
        _deployed_settings(environment, database_url=unparsable)

    assert DATABASE_PASSWORD not in str(raised.value)


@pytest.mark.parametrize("environment", LOCAL_ENVIRONMENTS)
def test_when_the_database_url_cannot_be_parsed_locally_then_it_is_not_judged(
    environment: str,
) -> None:
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy()."""
    built = _deployed_settings(environment, database_url="not-a-url")

    assert built.database_url == "not-a-url"
