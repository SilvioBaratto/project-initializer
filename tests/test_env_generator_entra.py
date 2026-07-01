"""Source-blind example tests for issue #2 — feat(env): emit ENTRA_* env block.

All tests are authored from the acceptance criteria and requirements.md only;
no implementation source was read during authorship (Red phase of TDD).

Acceptance criteria covered:
  AC-1  generate_env(framework, "entra", ...) emits a '# Microsoft Entra ID' block
        with ENTRA_TENANT_ID, ENTRA_API_CLIENT_ID, ENTRA_API_AUDIENCE,
        ENTRA_API_SCOPE, ENTRA_SPA_CLIENT_ID
  AC-2  entra mode emits local Docker DATABASE_URL; SUPABASE_DATABASE_URL and
        SUPABASE_URL are absent (for both fastapi and nestjs)
  AC-3  env_defaults.env carries ENTRA_* placeholder values — verified by
        checking the generated values are non-empty strings (populated, not blank)
  AC-4  python -m project_initializer.env_generator fastapi --auth entra --dest
        <path> exits 0 (standalone --auth choices include "entra")
  AC-5  The ENTRA_* block is absent for none / token / supabase modes (no regression)
"""

import subprocess
import sys

import pytest
from hypothesis import given, settings as hyp_settings, strategies as st

from project_initializer.env_generator import generate_env


# ---------------------------------------------------------------------------
# Constants derived from the acceptance criteria — not from any source file.
# ---------------------------------------------------------------------------

ENTRA_KEYS = [
    "ENTRA_TENANT_ID",
    "ENTRA_API_CLIENT_ID",
    "ENTRA_API_AUDIENCE",
    "ENTRA_API_SCOPE",
    "ENTRA_SPA_CLIENT_ID",
]

NON_ENTRA_AUTH_MODES = ["none", "token", "supabase"]
FRAMEWORKS = ["fastapi", "nestjs"]


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _generate_entra_env(tmp_path, framework):
    dest = tmp_path / "api" / ".env"
    dest.parent.mkdir(parents=True, exist_ok=True)
    generate_env(framework, "entra", dest=str(dest))
    return dest.read_text()


# ── AC-1a: '# Microsoft Entra ID' section header ────────────────────────────


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_when_generate_env_called_with_entra_then_microsoft_entra_id_header_is_emitted(
    tmp_path, framework
):
    """generate_env(framework, 'entra', ...) must write a '# Microsoft Entra ID' header."""
    content = _generate_entra_env(tmp_path, framework)
    assert "# Microsoft Entra ID" in content


# ── AC-1b: each of the five ENTRA_* keys is present ─────────────────────────


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("key", ENTRA_KEYS)
def test_when_generate_env_called_with_entra_then_entra_key_is_present(
    tmp_path, framework, key
):
    """generate_env(framework, 'entra', ...) must emit every required ENTRA_* key."""
    content = _generate_entra_env(tmp_path, framework)
    assert key in content


# ── AC-1c (property): all five keys present across all frameworks ─────────────


@given(st.sampled_from(FRAMEWORKS))
@hyp_settings(max_examples=10)
def test_when_entra_mode_and_any_framework_then_all_entra_keys_are_present(framework):
    """Invariant: all five ENTRA_* keys appear in entra output for every supported framework."""
    content = generate_env(framework, "entra")
    for key in ENTRA_KEYS:
        assert key in content, (
            f"Expected {key!r} to be present for framework={framework!r}"
        )


# ── AC-2a: local Docker DATABASE_URL is emitted ──────────────────────────────


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_when_generate_env_called_with_entra_then_database_url_is_emitted(
    tmp_path, framework
):
    """generate_env with entra must emit DATABASE_URL (local Docker DB, not Supabase)."""
    content = _generate_entra_env(tmp_path, framework)
    assert "DATABASE_URL" in content


# ── AC-2b: SUPABASE_DATABASE_URL must be absent for entra ────────────────────


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_when_generate_env_called_with_entra_then_supabase_database_url_is_absent(
    tmp_path, framework
):
    """generate_env with entra must NOT emit SUPABASE_DATABASE_URL."""
    content = _generate_entra_env(tmp_path, framework)
    assert "SUPABASE_DATABASE_URL" not in content


# ── AC-2c: SUPABASE_URL must be absent for entra ─────────────────────────────


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_when_generate_env_called_with_entra_then_supabase_url_is_absent(
    tmp_path, framework
):
    """generate_env with entra must NOT emit SUPABASE_URL."""
    content = _generate_entra_env(tmp_path, framework)
    assert "SUPABASE_URL" not in content


# ── AC-3: ENTRA_* values are populated (non-empty) — env_defaults carries them ─


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("key", ENTRA_KEYS)
def test_when_generate_env_called_with_entra_then_entra_key_has_non_empty_value(
    tmp_path, framework, key
):
    """Each ENTRA_* key must have a non-empty value (env_defaults.env ships placeholders).

    Assumption: 'populated rather than blank' means the value on the right-hand side
    of the KEY=VALUE line is at least one non-whitespace character.
    """
    content = _generate_entra_env(tmp_path, framework)
    for line in content.splitlines():
        if line.startswith(f"{key}="):
            value = line.split("=", 1)[1].strip()
            assert value != "", (
                f"{key} must not have an empty value for framework={framework!r}"
            )
            break
    else:
        pytest.fail(f"{key!r} not found in generated .env for framework={framework!r}")


# ── AC-4a: standalone invocation exits 0 ─────────────────────────────────────


def test_when_standalone_env_generator_called_with_auth_entra_then_it_exits_zero(
    tmp_path,
):
    """python -m project_initializer.env_generator fastapi --auth entra --dest <path>
    must exit with code 0 (i.e. 'entra' is a valid --auth choice)."""
    dest = tmp_path / "api" / ".env"
    dest.parent.mkdir(parents=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.env_generator",
            "fastapi",
            "--auth",
            "entra",
            "--dest",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit 0; stderr={result.stderr!r}; stdout={result.stdout!r}"
    )


# ── AC-4b: standalone invocation produces a non-empty file ───────────────────


def test_when_standalone_env_generator_called_with_auth_entra_then_file_is_written(
    tmp_path,
):
    """The standalone invocation must produce a non-empty .env file at the dest path."""
    dest = tmp_path / "api" / ".env"
    dest.parent.mkdir(parents=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.env_generator",
            "fastapi",
            "--auth",
            "entra",
            "--dest",
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert dest.exists(), "Destination file was not created"
    assert dest.stat().st_size > 0, "Destination file is empty"


# ── AC-5a: ENTRA_* block absent for non-entra modes (no regression) ──────────


@pytest.mark.parametrize("mode", NON_ENTRA_AUTH_MODES)
@pytest.mark.parametrize("key", ENTRA_KEYS)
def test_when_generate_env_called_with_non_entra_mode_then_entra_key_is_absent(
    tmp_path, mode, key
):
    """ENTRA_* keys must not appear for none / token / supabase modes (additive, no regression)."""
    dest = tmp_path / "api" / ".env"
    dest.parent.mkdir(parents=True)
    generate_env("fastapi", mode, dest=str(dest))
    content = dest.read_text()
    assert key not in content, f"{key!r} must be absent for auth mode {mode!r}"


# ── AC-5b (property): ENTRA_* absent for every non-entra mode ────────────────


@given(st.sampled_from(NON_ENTRA_AUTH_MODES))
@hyp_settings(max_examples=15)
def test_when_non_entra_auth_mode_then_no_entra_keys_appear_in_output(mode):
    """Invariant: no ENTRA_* key ever appears in the output for a non-entra mode."""
    auth = None if mode == "none" else mode
    content = generate_env("fastapi", auth)
    for key in ENTRA_KEYS:
        assert key not in content, f"{key!r} unexpectedly present for mode={mode!r}"
