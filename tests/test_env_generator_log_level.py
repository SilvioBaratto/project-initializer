"""Tests for LOG_LEVEL casing in env_generator output (issue #4).

Asserts that generate_env(...) for the NestJS variant:
  1. emits LOG_LEVEL=info (lowercase) by default when no value is supplied
  2. normalises any caller-supplied casing to lowercase in the emitted .env
"""

import pytest
from hypothesis import given, strategies as st

from project_initializer.env_generator import generate_env

_PINO_LEVELS = ["trace", "debug", "info", "warn", "error", "fatal"]

# Build all casings of valid pino level labels: lower, UPPER, Capitalised
_ALL_CASINGS = (
    _PINO_LEVELS
    + [lv.upper() for lv in _PINO_LEVELS]
    + [lv.capitalize() for lv in _PINO_LEVELS]
)


@pytest.mark.unit
def test_when_nestjs_env_generated_with_no_log_level_then_log_level_is_info():
    """when no LOG_LEVEL key exists in source_env, NestJS output contains LOG_LEVEL=info."""
    output = generate_env("nestjs", None, {})

    assert "LOG_LEVEL=info" in output


@pytest.mark.unit
def test_when_caller_supplies_uppercase_log_level_then_emitted_value_is_lowercase():
    """when LOG_LEVEL=INFO is in source_env, the emitted value is lowercased to info."""
    output = generate_env("nestjs", None, {"LOG_LEVEL": "INFO"})

    assert "LOG_LEVEL=info" in output


@pytest.mark.unit
def test_when_caller_supplies_mixed_case_log_level_then_emitted_value_is_lowercase():
    """when LOG_LEVEL=Debug is in source_env, the emitted value is lowercased to debug."""
    output = generate_env("nestjs", None, {"LOG_LEVEL": "Debug"})

    assert "LOG_LEVEL=debug" in output


@pytest.mark.unit
def test_when_fastapi_env_generated_with_uppercase_log_level_then_emitted_value_is_lowercase():
    """regression: normalization applies to FastAPI output too (shared line, not NestJS-only).

    templates-api-fastapi/docker-compose.yml hardcodes LOG_LEVEL: INFO inline (unaffected),
    but the generated api/.env must also be lowercase so FastAPI's .lower() calls stay consistent.
    """
    output = generate_env("fastapi", None, {"LOG_LEVEL": "INFO"})

    assert "LOG_LEVEL=info" in output


@pytest.mark.unit
@given(level=st.sampled_from(_ALL_CASINGS))
def test_when_any_cased_pino_level_supplied_then_emitted_log_level_is_always_lowercase(
    level: str,
) -> None:
    """for any casing of a pino level label, the emitted LOG_LEVEL is always lowercase.

    Invariant: generate_env('nestjs', ..., {'LOG_LEVEL': level}) contains
    LOG_LEVEL=<level.lower()> for every valid pino level in any casing.
    """
    output = generate_env("nestjs", None, {"LOG_LEVEL": level})

    assert f"LOG_LEVEL={level.lower()}" in output
