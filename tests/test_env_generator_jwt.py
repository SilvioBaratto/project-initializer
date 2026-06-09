"""Tests for JWT vars in env_generator output (issue #17).

Asserts that generate_env("fastapi", "token", ...) includes the three JWT
configuration variables, and that the non-token fastapi branch does NOT.
"""

import pytest

from project_initializer.env_generator import generate_env


@pytest.mark.unit
def test_when_token_auth_then_jwt_secret_key_is_present():
    """when auth=token, JWT_SECRET_KEY is included in the generated .env."""
    output = generate_env("fastapi", "token", {})

    assert "JWT_SECRET_KEY" in output


@pytest.mark.unit
def test_when_token_auth_then_jwt_algorithm_is_hs256():
    """when auth=token, JWT_ALGORITHM=HS256 is included in the generated .env."""
    output = generate_env("fastapi", "token", {})

    assert "JWT_ALGORITHM=HS256" in output


@pytest.mark.unit
def test_when_token_auth_then_access_token_expire_minutes_is_present():
    """when auth=token, ACCESS_TOKEN_EXPIRE_MINUTES=30 is included in the generated .env."""
    output = generate_env("fastapi", "token", {})

    assert "ACCESS_TOKEN_EXPIRE_MINUTES=30" in output


@pytest.mark.unit
def test_when_no_auth_then_jwt_vars_are_absent():
    """when auth=None (no token), JWT_SECRET_KEY is absent from the generated .env."""
    output = generate_env("fastapi", None, {})

    assert "JWT_SECRET_KEY" not in output
    assert "JWT_ALGORITHM" not in output
    assert "ACCESS_TOKEN_EXPIRE_MINUTES" not in output


@pytest.mark.unit
def test_when_token_auth_then_auth_token_is_also_present():
    """when auth=token, existing AUTH_TOKEN line is still emitted alongside JWT vars."""
    output = generate_env("fastapi", "token", {"AUTH_TOKEN": "mytoken"})

    assert "AUTH_TOKEN=mytoken" in output
    assert "JWT_SECRET_KEY" in output
