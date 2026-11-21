"""Unit tests of the Supabase authentication settings."""

import pytest
from pydantic import ValidationError

from app.infrastructure.auth_settings import (
    DEFAULT_AUTH_TIMEOUT_SECONDS,
    MAX_AUTH_TIMEOUT_SECONDS,
    AuthSettings,
)
from app.infrastructure.settings import Settings
from tests.auth_test_env import AUTH_TEST_ENV

pytestmark = pytest.mark.unit

REAL_URL = "https://abcdefghijklmnop.supabase.co"
REAL_KEY = "sb_publishable_0123456789"
SECRET_KEY = "sb_secret_0123456789"
DEPLOYED_ENVIRONMENTS = ["staging", "production"]
LOCAL_ENVIRONMENTS = ["development", "test"]


@pytest.fixture(autouse=True)
def unset_supabase_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide every Supabase variable, so defaults are what is tested.

    ``conftest.py`` sets the test project and a developer's shell may export any
    other setting; both would otherwise leak into the defaults asserted here.
    """
    setting_names = {field.upper() for field in AuthSettings.model_fields}
    for name in {*AUTH_TEST_ENV, *setting_names}:
        monkeypatch.delenv(name, raising=False)


def settings_for(environment: str, *, url: str, key: str) -> Settings:
    """Build the application settings for one stage and one Supabase project."""
    # A deployed stage refuses a database that is not TLS-protected, which is not
    # what these tests examine.
    return Settings(
        environment=environment,
        supabase_url=url,
        supabase_publishable_key=key,
        database_ssl_mode="require",
    )


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_when_a_deployed_stage_has_a_real_project_then_settings_are_accepted(
    environment,
):
    """when staging or production names a real https project, Settings builds.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    built = settings_for(environment, url=REAL_URL, key=REAL_KEY)

    assert built.supabase_url == REAL_URL


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize(
    ("url", "key", "named_setting"),
    [
        pytest.param("", REAL_KEY, "SUPABASE_URL", id="empty-url"),
        pytest.param("   ", REAL_KEY, "SUPABASE_URL", id="blank-url"),
        pytest.param(
            "https://your-project-ref.supabase.co",
            REAL_KEY,
            "SUPABASE_URL",
            id="placeholder-url",
        ),
        pytest.param(REAL_URL, "", "SUPABASE_PUBLISHABLE_KEY", id="empty-key"),
        pytest.param(
            REAL_URL,
            "your-supabase-publishable-key",
            "SUPABASE_PUBLISHABLE_KEY",
            id="placeholder-key",
        ),
        pytest.param(
            "http://abcdefghijklmnop.supabase.co", REAL_KEY, "https", id="plain-http"
        ),
        pytest.param(REAL_URL, SECRET_KEY, "SUPABASE_PUBLISHABLE_KEY", id="secret-key"),
    ],
)
def test_when_a_deployed_stage_has_no_real_project_then_settings_are_refused(
    environment, url, key, named_setting
):
    """when a deployed stage lacks a real https project, Settings names the setting.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    with pytest.raises(ValidationError, match=named_setting) as raised:
        settings_for(environment, url=url, key=key)

    assert REAL_KEY not in str(raised.value)
    assert SECRET_KEY not in str(raised.value)


@pytest.mark.parametrize("environment", LOCAL_ENVIRONMENTS)
def test_when_the_stage_is_local_then_an_unconfigured_project_is_accepted(environment):
    """when development or test has no Supabase values, Settings still builds.

    Validates app.infrastructure.auth_settings.AuthSettings.validate_auth_secrets().
    """
    built = settings_for(environment, url="", key="")

    assert (built.supabase_url, built.supabase_publishable_key) == ("", "")


def test_when_no_timeout_is_given_then_the_default_applies():
    """when SUPABASE_AUTH_TIMEOUT is unset, the default timeout is used.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    assert AuthSettings().supabase_auth_timeout == DEFAULT_AUTH_TIMEOUT_SECONDS


@pytest.mark.parametrize("timeout", [0.1, MAX_AUTH_TIMEOUT_SECONDS])
def test_when_the_timeout_is_within_bounds_then_it_is_accepted(timeout):
    """when the timeout is positive and at most the maximum, it is accepted.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    assert AuthSettings(supabase_auth_timeout=timeout).supabase_auth_timeout == timeout


@pytest.mark.parametrize("timeout", [0, -1, MAX_AUTH_TIMEOUT_SECONDS + 0.1])
def test_when_the_timeout_is_out_of_bounds_then_it_is_rejected(timeout):
    """when the timeout is zero, negative or above the maximum, validation fails.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    with pytest.raises(ValidationError):
        AuthSettings(supabase_auth_timeout=timeout)


def test_when_the_settings_are_listed_then_no_service_role_key_is_configurable():
    """when the fields are listed, only the URL, publishable key and timeout exist.

    Validates app.infrastructure.auth_settings.AuthSettings.
    """
    assert set(AuthSettings.model_fields) == {
        "supabase_url",
        "supabase_publishable_key",
        "supabase_auth_timeout",
    }
