"""
Source-blind example tests for the CLI entra-mode registration and
packaging criteria from issue #4 (templates-entra-nestjs scope).

Derived entirely from acceptance criteria — no implementation source read.

Skipped criteria:
  - "All tests pass"         — NOT VERIFIABLE (boilerplate suite gate)
  - "SOLID, clean code …"    — NOT VERIFIABLE (subjective prose)
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "project_initializer.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd or PROJECT_ROOT,
    )


# ===========================================================================
# Criterion: --auth entra is available as a fourth auth mode alongside
#            none / token / supabase
# ===========================================================================


def test_when_auth_entra_is_passed_to_cli_then_it_is_accepted_as_valid_mode(tmp_path):
    """
    --auth entra must not produce an 'invalid choice' or 'unrecognized' error.
    Assumption: the CLI exits with a non-2 code (argument error) when an invalid
    --auth value is supplied, so absence of exit-code 2 means the mode is registered.
    """
    result = _run_cli(
        "smoke-entra-nestjs",
        "--nestjs",
        "--auth",
        "entra",
        "--force",
        cwd=str(tmp_path),
    )
    assert result.returncode != 2, (
        f"--auth entra must be a recognised CLI argument; got stderr:\n{result.stderr}"
    )


@pytest.mark.parametrize("auth_mode", ["token", "supabase"])
def test_when_existing_auth_mode_is_used_then_it_is_still_accepted(tmp_path, auth_mode):
    """Existing modes must remain unchanged after adding entra."""
    result = _run_cli(
        "smoke-existing", "--fastapi", "--auth", auth_mode, "--force", cwd=str(tmp_path)
    )
    assert result.returncode != 2, (
        f"--auth {auth_mode} must remain a valid CLI argument; got stderr:\n{result.stderr}"
    )


def test_when_no_auth_is_passed_then_cli_still_accepts_base_mode(tmp_path):
    """The no-auth (none) mode must remain unchanged."""
    result = _run_cli("smoke-none", "--fastapi", "--force", cwd=str(tmp_path))
    assert result.returncode != 2, (
        f"Base (no --auth) mode must remain valid; got stderr:\n{result.stderr}"
    )


@pytest.mark.parametrize("scope", ["api", "frontend", "fullstack"])
def test_when_scope_is_used_without_entra_then_it_is_still_accepted(tmp_path, scope):
    """Every --scope combination must remain unchanged."""
    if scope == "frontend":
        args = ["smoke-scope", "--scope", scope, "--force"]
    else:
        args = ["smoke-scope", "--fastapi", "--scope", scope, "--force"]
    result = _run_cli(*args, cwd=str(tmp_path))
    assert result.returncode != 2, (
        f"--scope {scope} must remain valid; got stderr:\n{result.stderr}"
    )


# ===========================================================================
# Criterion: The three new overlay directories mirror the supabase overlay
#            layout 1:1 so copy_tree merges them with no special-casing
# ===========================================================================


@pytest.mark.parametrize(
    "overlay_dir",
    [
        "templates-entra-fastapi",
        "templates-entra-nestjs",
        "templates-entra-frontend",
    ],
)
def test_when_overlay_dirs_are_inspected_then_all_three_exist(overlay_dir):
    overlay = PROJECT_ROOT / "project_initializer" / overlay_dir
    assert overlay.is_dir(), (
        f"Overlay directory project_initializer/{overlay_dir}/ must exist"
    )


# ===========================================================================
# Criterion: pyproject.toml packages all three new overlay directories
# ===========================================================================


def test_when_pyproject_toml_is_read_then_entra_fastapi_overlay_is_packaged():
    text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "templates-entra-fastapi" in text, (
        "pyproject.toml must include templates-entra-fastapi in package-data"
    )


def test_when_pyproject_toml_is_read_then_entra_nestjs_overlay_is_packaged():
    text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "templates-entra-nestjs" in text, (
        "pyproject.toml must include templates-entra-nestjs in package-data"
    )


def test_when_pyproject_toml_is_read_then_entra_frontend_overlay_is_packaged():
    text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "templates-entra-frontend" in text, (
        "pyproject.toml must include templates-entra-frontend in package-data"
    )


# ===========================================================================
# Criterion: MANIFEST.in packages all three new overlay directories
# ===========================================================================


def test_when_manifest_in_is_read_then_entra_fastapi_overlay_is_included():
    text = (PROJECT_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "templates-entra-fastapi" in text, (
        "MANIFEST.in must include a recursive-include for templates-entra-fastapi"
    )


def test_when_manifest_in_is_read_then_entra_nestjs_overlay_is_included():
    text = (PROJECT_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "templates-entra-nestjs" in text, (
        "MANIFEST.in must include a recursive-include for templates-entra-nestjs"
    )


def test_when_manifest_in_is_read_then_entra_frontend_overlay_is_included():
    text = (PROJECT_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "templates-entra-frontend" in text, (
        "MANIFEST.in must include a recursive-include for templates-entra-frontend"
    )


# ===========================================================================
# Criterion: No client secret is present in either backend overlay
# ===========================================================================


@pytest.mark.parametrize(
    "overlay_name",
    [
        "templates-entra-fastapi",
        "templates-entra-nestjs",
    ],
)
def test_when_backend_overlay_is_scanned_then_no_client_secret_key_appears(
    overlay_name,
):
    """
    Assumption: 'no client secret' means neither the variable name CLIENT_SECRET
    nor clientSecret appears in any non-comment line across the overlay.
    """
    # NestJS overlays keep files under an api/ subdirectory
    sub = "api" if "nestjs" in overlay_name else ""
    overlay_dir = (
        PROJECT_ROOT / "project_initializer" / overlay_name / sub
        if sub
        else PROJECT_ROOT / "project_initializer" / overlay_name
    )
    combined_parts = []
    for path in overlay_dir.rglob("*"):
        if path.is_file():
            try:
                combined_parts.append(
                    path.read_text(encoding="utf-8", errors="replace")
                )
            except Exception:
                pass
    combined = "\n".join(combined_parts)
    non_comment_lines = "\n".join(
        line
        for line in combined.splitlines()
        if not line.strip().startswith("#") and not line.strip().startswith("//")
    )
    import re

    assert not re.search(
        r"CLIENT_SECRET|clientSecret|client_secret", non_comment_lines, re.IGNORECASE
    ), f"{overlay_name} must contain no client secret value or key"
