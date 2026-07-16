"""Unit tests for the project-initializer Typer CLI flag surface.

The argparse ``build_parser`` was replaced by a Typer app + questionary wizard.
These tests drive the app through Typer's ``CliRunner`` (stdin is a non-TTY pipe,
so the wizard is skipped and unset options fall back to defaults) and capture the
resolved (scope, framework, auth, async_db) via a monkeypatched ``copy_template``.
"""

import pytest
from typer.testing import CliRunner

import project_initializer.cli as cli
from project_initializer.cli import SCOPES, app

runner = CliRunner()


@pytest.fixture()
def captured(monkeypatch):
    """Capture the kwargs copy_template is called with (no files are written)."""
    calls = {}

    def spy(dest_dir, project_name=None, **kwargs):
        calls.update(kwargs)
        calls["project_name"] = project_name

    monkeypatch.setattr(cli, "copy_template", spy)
    return calls


def run(argv):
    """Invoke the CLI non-interactively (CliRunner stdin is not a TTY)."""
    return runner.invoke(app, argv)


def test_when_no_scope_given_default_is_fullstack(captured):
    result = run(["myapp"])
    assert result.exit_code == 0
    assert captured["scope"] == "fullstack"


@pytest.mark.parametrize("scope", SCOPES)
def test_when_scope_value_given_it_is_parsed(captured, scope):
    result = run(["myapp", "--scope", scope])
    assert result.exit_code == 0
    assert captured["scope"] == scope


def test_scopes_constant_holds_the_three_supported_values():
    assert SCOPES == ("fullstack", "api", "frontend")


def test_when_invalid_scope_given_exit_is_nonzero():
    result = run(["myapp", "--scope", "bogus"])
    assert result.exit_code != 0


def test_when_no_framework_flag_given_framework_defaults_to_fastapi(captured):
    result = run(["myapp"])
    assert result.exit_code == 0
    assert captured["framework"] == "fastapi"


def test_when_fastapi_flag_given_framework_is_fastapi(captured):
    result = run(["myapp", "--fastapi"])
    assert result.exit_code == 0
    assert captured["framework"] == "fastapi"


def test_when_nestjs_flag_given_framework_is_nestjs(captured):
    result = run(["myapp", "--nestjs"])
    assert result.exit_code == 0
    assert captured["framework"] == "nestjs"


def test_when_framework_option_given_it_is_parsed(captured):
    result = run(["myapp", "--framework", "nestjs"])
    assert result.exit_code == 0
    assert captured["framework"] == "nestjs"


def test_when_both_framework_flags_given_exit_is_nonzero():
    result = run(["myapp", "--fastapi", "--nestjs"])
    assert result.exit_code != 0


def test_when_project_name_given_it_is_parsed(captured):
    result = run(["myapp"])
    assert result.exit_code == 0
    assert captured["project_name"] == "myapp"


def test_when_auth_token_given_it_is_parsed(captured):
    result = run(["myapp", "--auth", "token"])
    assert result.exit_code == 0
    assert captured["auth"] == "token"


def test_when_auth_supabase_given_it_is_parsed(captured):
    result = run(["myapp", "--auth", "supabase"])
    assert result.exit_code == 0
    assert captured["auth"] == "supabase"


def test_when_auth_omitted_it_is_none(captured):
    result = run(["myapp"])
    assert result.exit_code == 0
    assert captured["auth"] is None


def test_when_invalid_auth_given_exit_is_nonzero():
    result = run(["myapp", "--auth", "bogus"])
    assert result.exit_code != 0


def test_when_async_db_flag_given_it_is_true(captured):
    result = run(["myapp", "--async-db"])
    assert result.exit_code == 0
    assert captured["async_db"] is True


def test_when_async_db_flag_omitted_it_is_false(captured):
    result = run(["myapp"])
    assert result.exit_code == 0
    assert captured["async_db"] is False


def test_when_version_flag_given_it_prints_version_and_exits():
    result = run(["--version"])
    assert result.exit_code == 0
    assert "project-initializer" in result.stdout


def test_when_no_project_name_given_default_is_current_dir(captured, monkeypatch, tmp_path):
    """Omitting the project name scaffolds into the current directory (project_name='.')."""
    # cwd is non-empty in this repo; chdir to an empty tmp dir so the
    # "directory not empty" guard does not prompt and abort.
    monkeypatch.chdir(tmp_path)
    result = run([])
    assert result.exit_code == 0
    assert captured["project_name"] == "."


def test_when_force_flag_given_scaffold_runs_without_prompt(captured, monkeypatch, tmp_path):
    """`-f/--force` scaffolds into a non-empty directory without the overwrite prompt."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "existing.txt").write_text("x", encoding="utf-8")
    # Without --force this would call input() and, on an empty stdin, abort;
    # with --force the guard is skipped and copy_template is reached.
    result = run(["myapp", "--force"])
    assert result.exit_code == 0
    assert captured["project_name"] == "myapp"
