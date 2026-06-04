"""Unit tests for the project-initializer argument parser."""

import pytest

from project_initializer.cli import SCOPES, build_parser


def parse(argv):
    return build_parser().parse_args(argv)


def test_when_no_scope_given_default_is_fullstack():
    assert parse([]).scope == "fullstack"


@pytest.mark.parametrize("scope", SCOPES)
def test_when_scope_value_given_it_is_parsed(scope):
    assert parse(["--scope", scope]).scope == scope


def test_scopes_constant_holds_the_three_supported_values():
    assert SCOPES == ("fullstack", "api", "frontend")


def test_when_invalid_scope_given_system_exit_is_raised():
    with pytest.raises(SystemExit):
        parse(["--scope", "bogus"])


def test_when_no_framework_flag_given_framework_is_none():
    assert parse([]).framework is None


def test_when_fastapi_flag_given_framework_is_fastapi():
    assert parse(["--fastapi"]).framework == "fastapi"


def test_when_nestjs_flag_given_framework_is_nestjs():
    assert parse(["--nestjs"]).framework == "nestjs"


def test_when_both_framework_flags_given_system_exit_is_raised():
    with pytest.raises(SystemExit):
        parse(["--fastapi", "--nestjs"])


def test_when_no_project_name_given_default_is_current_dir():
    assert parse([]).project_name == "."


def test_when_project_name_given_it_is_parsed():
    assert parse(["myapp"]).project_name == "myapp"


def test_when_force_flag_given_it_is_true():
    assert parse(["-f"]).force is True
    assert parse([]).force is False


def test_when_auth_flag_given_alone_const_is_token():
    assert parse(["--auth"]).auth == "token"


def test_when_auth_supabase_given_it_is_parsed():
    assert parse(["--auth", "supabase"]).auth == "supabase"


def test_when_auth_omitted_it_is_none():
    assert parse([]).auth is None


def test_when_invalid_auth_given_system_exit_is_raised():
    with pytest.raises(SystemExit):
        parse(["--auth", "bogus"])
