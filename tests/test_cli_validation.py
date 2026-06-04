"""Unit tests for cross-flag --scope validation."""

import sys

import pytest

from project_initializer.cli import main, validate_scope


def test_when_frontend_scope_has_explicit_framework_error_is_returned():
    errors = validate_scope("frontend", "fastapi", None)
    assert errors
    assert all(isinstance(message, str) for message in errors)


def test_when_frontend_scope_has_auth_error_is_returned():
    assert validate_scope("frontend", None, "token")
    assert validate_scope("frontend", None, "supabase")


def test_when_frontend_scope_alone_no_error_is_returned():
    assert validate_scope("frontend", None, None) == []


@pytest.mark.parametrize("scope", ["api", "fullstack"])
@pytest.mark.parametrize("framework", [None, "fastapi", "nestjs"])
@pytest.mark.parametrize("auth", [None, "token", "supabase"])
def test_when_api_or_fullstack_scope_any_options_no_error(scope, framework, auth):
    assert validate_scope(scope, framework, auth) == []


def test_when_frontend_scope_and_nestjs_error_is_returned():
    assert validate_scope("frontend", "nestjs", None)


def test_when_frontend_scope_conflicts_main_exits_non_zero(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["project-initializer", "app", "--scope", "frontend", "--fastapi"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
