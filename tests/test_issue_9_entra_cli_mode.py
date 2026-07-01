"""
Source-blind tests for issue #9 — criterion 1:
  --auth entra is available as a fourth auth mode alongside none / token / supabase,
  and all existing modes plus every --scope combination remain unchanged.

Tests are authored from the acceptance criteria only; no implementation source was read.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

# ---------------------------------------------------------------------------
# Helpers — call the CLI without importing implementation internals
# ---------------------------------------------------------------------------

_CLI = [sys.executable, "-m", "project_initializer.cli"]
_ROOT = Path(__file__).parent.parent


def _run(*args, cwd=None):
    return subprocess.run(
        [*_CLI, *args],
        capture_output=True,
        text=True,
        cwd=cwd or _ROOT,
    )


# ---------------------------------------------------------------------------
# Criterion 1a: --auth entra is accepted as a valid mode
# ---------------------------------------------------------------------------


def test_when_auth_entra_passed_then_cli_does_not_error_on_unknown_mode(tmp_path):
    """--auth entra must be accepted by argparse without an 'invalid choice' error."""
    result = _run("project-entra-smoke", "--auth", "entra", "--force", cwd=tmp_path)
    # An unknown auth value produces a non-zero exit with 'invalid choice' in stderr.
    # We only assert the absence of that specific rejection, not full success (the
    # overlay directories may not exist yet in the Red phase).
    assert "invalid choice" not in result.stderr
    assert "invalid choice: 'entra'" not in result.stderr


# ---------------------------------------------------------------------------
# Criterion 1b: existing modes remain accepted unchanged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_mode", ["token", "supabase"])
def test_when_existing_auth_mode_passed_then_cli_still_accepts_it(tmp_path, auth_mode):
    """Each pre-existing auth mode must remain a valid choice after the entra addition."""
    result = _run(
        f"project-smoke-{auth_mode}", "--auth", auth_mode, "--force", cwd=tmp_path
    )
    assert "invalid choice" not in result.stderr
    assert f"invalid choice: '{auth_mode}'" not in result.stderr


# ---------------------------------------------------------------------------
# Criterion 1c: every --scope combination remains unchanged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scope", ["api", "frontend", "fullstack"])
def test_when_scope_passed_then_cli_still_accepts_it(tmp_path, scope):
    """Each --scope value must remain valid after adding the entra auth mode."""
    if scope == "frontend":
        args = [f"project-scope-{scope}", "--scope", scope, "--force"]
    else:
        args = [f"project-scope-{scope}", "--scope", scope, "--force"]
    result = _run(*args, cwd=tmp_path)
    assert f"invalid choice: '{scope}'" not in result.stderr


@pytest.mark.parametrize(
    "scope,framework",
    [
        ("api", "--fastapi"),
        ("api", "--nestjs"),
        ("fullstack", "--fastapi"),
        ("fullstack", "--nestjs"),
    ],
)
def test_when_scope_and_framework_combined_then_cli_still_accepts_combination(
    tmp_path, scope, framework
):
    """Framework + scope combos must remain valid after the entra addition."""
    result = _run(
        f"project-combo-{scope}",
        framework,
        "--scope",
        scope,
        "--force",
        cwd=tmp_path,
    )
    assert "invalid choice" not in result.stderr


# ---------------------------------------------------------------------------
# Criterion 1d: no mode other than the four valid ones is accepted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_mode", ["oauth", "azure", "jwt", ""])
def test_when_unknown_auth_mode_passed_then_cli_rejects_it(tmp_path, bad_mode):
    """Auth modes outside {none, token, supabase, entra} must still be rejected."""
    if bad_mode == "":
        pytest.skip("empty string is a shell concern, not a Python argparse concern")
    result = _run("project-bad", "--auth", bad_mode, "--force", cwd=tmp_path)
    assert result.returncode != 0
    assert "invalid choice" in result.stderr


# ---------------------------------------------------------------------------
# Property: any valid auth mode value is stable across repeated CLI invocations
# ---------------------------------------------------------------------------


@given(
    auth_mode=st.sampled_from(["entra", "token", "supabase"]),
    framework=st.sampled_from(["--fastapi", "--nestjs"]),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_when_valid_auth_mode_used_then_rejected_for_auth_arg_is_never_raised(
    tmp_path, auth_mode, framework
):
    """For any valid auth mode the CLI must never emit 'invalid choice' for --auth."""
    result = _run("prop-smoke", framework, "--auth", auth_mode, "--force", cwd=tmp_path)
    assert "invalid choice" not in result.stderr
