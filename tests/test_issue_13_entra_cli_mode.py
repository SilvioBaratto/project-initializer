"""
Issue #13 — Criterion: --auth entra is available as a fourth auth mode alongside none/token/supabase,
and all existing modes plus every --scope combination remain unchanged.
"""

import subprocess
import sys


def _cli_module():
    """Import cli without executing it as __main__."""
    import project_initializer.cli as cli

    return cli


def test_when_entra_is_queried_then_it_is_a_valid_auth_mode():
    cli = _cli_module()
    assert "entra" in cli.AUTH_MODES


def test_when_all_four_auth_modes_are_checked_then_none_token_supabase_entra_are_present():
    """The four auth modes are: 'no auth' (absence of --auth, i.e. default None) plus the
    three named modes token/supabase/entra. Only the named modes live in AUTH_MODES —
    'none' is modelled as the argparse default, not as a string choice."""
    cli = _cli_module()
    for mode in ("token", "supabase", "entra"):
        assert mode in cli.AUTH_MODES, f"expected auth mode {mode!r} in AUTH_MODES"
    assert "none" not in cli.AUTH_MODES, (
        "'no auth' is the default (None), not a named mode"
    )


def test_when_existing_modes_are_checked_then_none_token_supabase_remain_unchanged():
    """token / supabase must still be present so existing projects keep working;
    'no auth' remains the default (absence of --auth)."""
    cli = _cli_module()
    for mode in ("token", "supabase"):
        assert mode in cli.AUTH_MODES


def test_when_entra_and_fastapi_args_are_passed_then_cli_accepts_without_error(
    tmp_path,
):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            str(tmp_path / "out"),
            "--fastapi",
            "--auth",
            "entra",
            "--force",
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr


def test_when_entra_and_nestjs_args_are_passed_then_cli_accepts_without_error(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            str(tmp_path / "out"),
            "--nestjs",
            "--auth",
            "entra",
            "--force",
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr


def test_when_entra_with_scope_api_is_passed_then_cli_accepts_without_error(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            str(tmp_path / "out"),
            "--fastapi",
            "--auth",
            "entra",
            "--scope",
            "api",
            "--force",
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr


def test_when_existing_fastapi_no_auth_is_passed_then_cli_still_accepts(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            str(tmp_path / "out"),
            "--fastapi",
            "--force",
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr


def test_when_existing_nestjs_token_auth_is_passed_then_cli_still_accepts(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            str(tmp_path / "out"),
            "--nestjs",
            "--auth",
            "token",
            "--force",
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr


def test_when_existing_supabase_fastapi_is_passed_then_cli_still_accepts(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            str(tmp_path / "out"),
            "--fastapi",
            "--auth",
            "supabase",
            "--force",
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr


def test_when_scope_frontend_alone_is_passed_then_cli_still_accepts(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            str(tmp_path / "out"),
            "--scope",
            "frontend",
            "--force",
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr
