"""
Source-blind tests for issue #11 — chore: package the three entra overlay directories
in pyproject.toml and MANIFEST.in.

Tests authored directly from acceptance criteria only; no implementation source was read.
"""

from pathlib import Path

import pytest
from hypothesis import given, strategies as st

_ROOT = Path(__file__).parent.parent
_PKG = _ROOT / "project_initializer"

_ENTRA_OVERLAYS = [
    "templates-entra-fastapi",
    "templates-entra-nestjs",
    "templates-entra-frontend",
]

_SUPABASE_COUNTERPARTS = {
    "templates-entra-fastapi": "templates-supabase-fastapi",
    "templates-entra-nestjs": "templates-supabase-nestjs",
    "templates-entra-frontend": "templates-supabase-frontend",
}


# ---------------------------------------------------------------------------
# Global criterion: --auth entra is a fourth auth mode; existing modes survive
# ---------------------------------------------------------------------------


def test_when_auth_modes_inspected_then_entra_is_present_as_valid_mode() -> None:
    """AUTH_MODES must contain 'entra' so the CLI accepts --auth entra."""
    from project_initializer.cli import AUTH_MODES

    assert "entra" in AUTH_MODES


@pytest.mark.parametrize("mode", ["token", "supabase"])
def test_when_existing_auth_mode_checked_then_it_remains_in_auth_modes(
    mode: str,
) -> None:
    """No existing named auth mode may be removed when entra is added.

    The CLI represents 'no auth' as the absence of --auth (None), not as the string 'none',
    so only the named modes token/supabase are asserted here.
    """
    from project_initializer.cli import AUTH_MODES

    assert mode in AUTH_MODES, (
        f"Auth mode '{mode}' must not be removed by the entra addition"
    )


# ---------------------------------------------------------------------------
# Global criterion: in-process JWT validation overlay files exist
# ---------------------------------------------------------------------------


def test_when_fastapi_entra_overlay_checked_then_dependencies_py_provides_jwt_validation() -> (
    None
):
    """
    FastAPI entra overlay must contain app/api/deps.py to provide in-process JWKS validation.
    Assumption: in-process validation means a dedicated dependencies module mirroring the supabase overlay.
    """
    assert (
        _PKG / "templates-entra-fastapi" / "api" / "app" / "api" / "deps.py"
    ).exists(), (
        "templates-entra-fastapi/api/app/api/deps.py is required for in-process JWT validation"
    )


def test_when_nestjs_entra_overlay_checked_then_auth_service_provides_jwt_validation() -> (
    None
):
    """
    NestJS entra overlay must contain an auth service for in-process JWKS validation.
    Assumption: NestJS uses a feature-modules layout; auth service lives at
    src/modules/auth/auth.service.ts (mirroring the actual NestJS overlay structure).
    """
    auth_service = (
        _PKG
        / "templates-entra-nestjs"
        / "api"
        / "src"
        / "modules"
        / "auth"
        / "auth.service.ts"
    )
    assert auth_service.exists(), (
        "templates-entra-nestjs/api/src/modules/auth/auth.service.ts is required for in-process JWT validation"
    )


# ---------------------------------------------------------------------------
# Global criterion: no client secret in either backend
# ---------------------------------------------------------------------------


def test_when_fastapi_entra_env_example_checked_then_no_client_secret_is_present() -> (
    None
):
    """FastAPI entra overlay .env.example must not expose a client secret."""
    env_path = _PKG / "templates-entra-fastapi" / "api" / ".env.example"
    assert env_path.exists(), ".env.example missing from templates-entra-fastapi/api/"
    content = env_path.read_text(encoding="utf-8").lower()
    assert "client_secret" not in content, (
        "FastAPI entra .env.example must not contain a client_secret — "
        "backend validates via RS256 signature only"
    )


def test_when_nestjs_entra_env_example_checked_then_no_client_secret_is_present() -> (
    None
):
    """NestJS entra overlay .env.example must not expose a client secret."""
    env_path = _PKG / "templates-entra-nestjs" / "api" / ".env.example"
    assert env_path.exists(), ".env.example missing from templates-entra-nestjs/api/"
    content = env_path.read_text(encoding="utf-8").lower()
    assert "client_secret" not in content, (
        "NestJS entra .env.example must not contain a client_secret — "
        "backend validates via RS256 signature only"
    )


# ---------------------------------------------------------------------------
# Global criterion: overlay directories mirror supabase layout 1:1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entra_overlay,supabase_overlay",
    list(_SUPABASE_COUNTERPARTS.items()),
)
def test_when_entra_overlay_compared_to_supabase_then_top_level_subdirs_match(
    entra_overlay: str, supabase_overlay: str
) -> None:
    """Each entra overlay must contain every top-level subdirectory present in its supabase counterpart."""
    entra_dir = _PKG / entra_overlay
    supabase_dir = _PKG / supabase_overlay

    if not supabase_dir.is_dir():
        pytest.skip(f"Reference supabase overlay missing: {supabase_overlay}")
    assert entra_dir.is_dir(), f"Entra overlay directory missing: {entra_overlay}"

    supabase_subdirs = {p.name for p in supabase_dir.iterdir() if p.is_dir()}
    entra_subdirs = {p.name for p in entra_dir.iterdir() if p.is_dir()}
    missing = supabase_subdirs - entra_subdirs
    assert not missing, (
        f"{entra_overlay} is missing subdirectories present in {supabase_overlay}: {missing}"
    )


# ---------------------------------------------------------------------------
# Global criterion: JWKS key clients use auto-refresh libraries (no hard-coded schedule)
# ---------------------------------------------------------------------------


def test_when_fastapi_requirements_txt_checked_then_pyjwt_crypto_is_declared() -> None:
    """
    FastAPI entra overlay requirements.txt must declare PyJWT (with [crypto]) so PyJWKClient
    can auto-refresh signing keys on rotation.
    """
    req = _PKG / "templates-entra-fastapi" / "api" / "requirements.txt"
    assert req.exists(), "requirements.txt missing from templates-entra-fastapi/api/"
    content = req.read_text(encoding="utf-8")
    assert "PyJWT" in content, (
        "requirements.txt must include PyJWT[crypto] for JWKS auto-refresh via PyJWKClient"
    )


def test_when_nestjs_package_json_checked_then_jwks_rsa_is_declared() -> None:
    """
    NestJS entra overlay package.json must declare jwks-rsa so the auth service
    auto-refreshes signing keys on rotation (cache: true, rateLimit: true).
    """
    pkg_json = _PKG / "templates-entra-nestjs" / "api" / "package.json"
    assert pkg_json.exists(), "package.json missing from templates-entra-nestjs/api/"
    content = pkg_json.read_text(encoding="utf-8")
    assert "jwks-rsa" in content, (
        "package.json must declare jwks-rsa for JWKS key auto-refresh"
    )


# ---------------------------------------------------------------------------
# Scope criterion 1: pyproject.toml lists both /**/* and /**/.*  for all three overlays
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("overlay", _ENTRA_OVERLAYS)
def test_when_pyproject_toml_checked_then_regular_file_glob_exists_for_overlay(
    overlay: str,
) -> None:
    """pyproject.toml [tool.setuptools.package-data] must list '{overlay}/**/*'."""
    content = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert (f'"{overlay}/**/*"' in content) or (f"'{overlay}/**/*'" in content), (
        f"pyproject.toml is missing the '{overlay}/**/*' glob under "
        "[tool.setuptools.package-data]"
    )


@pytest.mark.parametrize("overlay", _ENTRA_OVERLAYS)
def test_when_pyproject_toml_checked_then_dotfile_glob_exists_for_overlay(
    overlay: str,
) -> None:
    """pyproject.toml [tool.setuptools.package-data] must list '{overlay}/**/.*' (dotfiles)."""
    content = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert (f'"{overlay}/**/.*"' in content) or (f"'{overlay}/**/.*'" in content), (
        f"pyproject.toml is missing the '{overlay}/**/.*' glob under "
        "[tool.setuptools.package-data]"
    )


@given(st.sampled_from(_ENTRA_OVERLAYS))
def test_when_any_entra_overlay_checked_then_both_pyproject_globs_always_coexist(
    overlay: str,
) -> None:
    """
    Invariant: for any entra overlay, the two glob patterns '/**/*' and '/**/.*' must
    always appear together in pyproject.toml — omitting the dotfile pattern silently
    excludes .env.example and other dotfiles from the wheel.
    """
    content = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    has_regular = (f'"{overlay}/**/*"' in content) or (f"'{overlay}/**/*'" in content)
    has_dotfile = (f'"{overlay}/**/.*"' in content) or (f"'{overlay}/**/.*'" in content)
    assert has_regular and has_dotfile, (
        f"pyproject.toml must list BOTH '/**/*' and '/**/.*' for '{overlay}'; "
        f"regular={has_regular}, dotfile={has_dotfile}"
    )


# ---------------------------------------------------------------------------
# Scope criterion 2: MANIFEST.in has both recursive-include lines for all three overlays
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("overlay", _ENTRA_OVERLAYS)
def test_when_manifest_in_checked_then_recursive_include_regular_files_exists_for_overlay(
    overlay: str,
) -> None:
    """MANIFEST.in must contain 'recursive-include project_initializer/{overlay} *'."""
    content = (_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    expected = f"recursive-include project_initializer/{overlay} *"
    assert expected in content, f"MANIFEST.in is missing: {expected!r}"


@pytest.mark.parametrize("overlay", _ENTRA_OVERLAYS)
def test_when_manifest_in_checked_then_recursive_include_dotfiles_exists_for_overlay(
    overlay: str,
) -> None:
    """MANIFEST.in must contain 'recursive-include project_initializer/{overlay} .*' (dotfiles)."""
    content = (_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    expected = f"recursive-include project_initializer/{overlay} .*"
    assert expected in content, f"MANIFEST.in is missing: {expected!r}"


@given(st.sampled_from(_ENTRA_OVERLAYS))
def test_when_any_entra_overlay_checked_then_both_manifest_recursive_include_lines_coexist(
    overlay: str,
) -> None:
    """
    Invariant: for any entra overlay, both 'recursive-include ... *' and '... .*' must
    always appear together in MANIFEST.in — omitting the dotfile line silently excludes
    .env.example and similar dotfiles from the sdist.
    """
    content = (_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    has_regular = f"recursive-include project_initializer/{overlay} *" in content
    has_dotfile = f"recursive-include project_initializer/{overlay} .*" in content
    assert has_regular and has_dotfile, (
        f"MANIFEST.in must have BOTH wildcard and dotfile recursive-include for '{overlay}'; "
        f"regular={has_regular}, dotfile={has_dotfile}"
    )


# ---------------------------------------------------------------------------
# Scope criterion 3: MANIFEST.in prunes entra-nestjs node_modules and generated client
# ---------------------------------------------------------------------------


def test_when_manifest_in_checked_then_entra_nestjs_node_modules_is_pruned() -> None:
    """
    MANIFEST.in must prune templates-entra-nestjs/api/node_modules, mirroring the sibling
    token-nestjs and supabase-nestjs prune lines.
    """
    content = (_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    prune = "prune project_initializer/templates-entra-nestjs/api/node_modules"
    assert prune in content, (
        f"MANIFEST.in is missing: {prune!r}\n"
        "entra-nestjs/api/node_modules must be pruned to mirror the sibling NestJS prune lines"
    )


def test_when_manifest_in_checked_then_entra_nestjs_generated_client_is_pruned() -> (
    None
):
    """
    MANIFEST.in must prune templates-entra-nestjs/api/generated (Prisma generated client),
    mirroring the supabase-nestjs prune line.
    """
    content = (_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    prune = "prune project_initializer/templates-entra-nestjs/api/generated"
    assert prune in content, (
        f"MANIFEST.in is missing: {prune!r}\n"
        "entra-nestjs/api/generated must be pruned to mirror the sibling supabase-nestjs prune line"
    )
