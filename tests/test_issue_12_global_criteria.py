"""
Source-blind tests for issue #12 global acceptance criteria.
Derived exclusively from the spec — no implementation source was read.

Criteria covered:
  C1 — `--auth entra` is available as a fourth auth mode; existing modes unchanged.
  C2 — FastAPI + NestJS overlays validate Entra v2 JWT in-process (RS256, aud, iss,
        exp/nbf, tid, scp); 401 on failure, 403 on missing scope.
  C3 — No client secret in either backend; only browser-safe values in environment.ts.
  C4 — Three new overlay dirs mirror supabase layout; pyproject.toml + MANIFEST.in
        package all three.
  C5 — JWKS clients auto-refresh (PyJWKClient / jwks-rsa cache+rateLimit); no
        hard-coded refresh schedule.
"""

import re
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
PKG_DIR = REPO_ROOT / "project_initializer"
TESTS_DIR = REPO_ROOT / "tests"

FASTAPI_OVERLAY = PKG_DIR / "templates-entra-fastapi"
NESTJS_OVERLAY = PKG_DIR / "templates-entra-nestjs"
FRONTEND_OVERLAY = PKG_DIR / "templates-entra-frontend"
SUPABASE_FASTAPI_OVERLAY = PKG_DIR / "templates-supabase-fastapi"
SUPABASE_NESTJS_OVERLAY = PKG_DIR / "templates-supabase-nestjs"
SUPABASE_FRONTEND_OVERLAY = PKG_DIR / "templates-supabase-frontend"

PYPROJECT = REPO_ROOT / "pyproject.toml"
MANIFEST = REPO_ROOT / "MANIFEST.in"


def _overlay_relative_paths(overlay_dir: Path) -> set[str]:
    """Return all file paths relative to the overlay root."""
    return {
        str(p.relative_to(overlay_dir)) for p in overlay_dir.rglob("*") if p.is_file()
    }


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# C1 — `--auth entra` recognised as a valid CLI mode
# ---------------------------------------------------------------------------


def test_when_auth_entra_mode_registered_then_it_is_accepted_by_cli():
    """
    Criterion: `--auth entra` is available as a fourth auth mode.
    We verify that the CLI module exports a collection of accepted auth modes
    that contains "entra" alongside the three existing modes.
    """
    import importlib

    cli = importlib.import_module("project_initializer.cli")
    auth_modes = getattr(cli, "AUTH_MODES", None)
    assert auth_modes is not None, "AUTH_MODES not found in project_initializer.cli"
    assert "entra" in auth_modes, f"'entra' not in AUTH_MODES: {auth_modes}"


def test_when_auth_entra_added_then_existing_modes_are_still_present():
    """
    Criterion: all existing modes (none / token / supabase) remain unchanged.
    """
    import importlib

    cli = importlib.import_module("project_initializer.cli")
    auth_modes = set(getattr(cli, "AUTH_MODES", []))
    for mode in ("token", "supabase"):
        assert mode in auth_modes, (
            f"Existing auth mode '{mode}' was removed from AUTH_MODES"
        )


def test_when_scope_combinations_enumerated_then_all_prior_scopes_still_valid():
    """
    Criterion: every --scope combination remains unchanged.
    The CLI must still recognise 'fullstack', 'api', and 'frontend' scopes.
    """
    import importlib

    cli = importlib.import_module("project_initializer.cli")
    scope_attr = getattr(cli, "SCOPES", None) or getattr(cli, "SCOPE_CHOICES", None)
    if scope_attr is None:
        pytest.skip(
            "No SCOPES / SCOPE_CHOICES constant found; scope validation tested elsewhere"
        )
    scope_set = set(scope_attr)
    for scope in ("fullstack", "api", "frontend"):
        assert scope in scope_set, f"Existing scope '{scope}' was removed"


# ---------------------------------------------------------------------------
# C2 — FastAPI overlay: RS256 / v2 JWT validation, 401/403 responses
# ---------------------------------------------------------------------------


class TestFastapiOverlayJwtValidation:
    """Tests against the template source files — not a running server."""

    def _deps(self) -> str:
        path = FASTAPI_OVERLAY / "api" / "app" / "api" / "deps.py"
        assert path.exists(), f"dependencies.py not found at {path}"
        return _read(path)

    def test_when_fastapi_overlay_present_then_pyjwt_crypto_in_requirements(self):
        """Criterion: RS256 validation uses PyJWT[crypto] (signature-only, in-process)."""
        req_candidates = list((FASTAPI_OVERLAY / "api").rglob("requirements*.txt"))
        assert req_candidates, (
            "No requirements*.txt found under templates-entra-fastapi/api/"
        )
        text = "\n".join(_read(p) for p in req_candidates)
        assert "PyJWT" in text or "pyjwt" in text.lower(), (
            "PyJWT not declared in entra-fastapi requirements"
        )

    def test_when_fastapi_dependencies_present_then_rs256_algorithm_is_enforced(self):
        """Criterion: signature validated against cached JWKS using RS256."""
        src = self._deps()
        assert "RS256" in src, "RS256 algorithm not referenced in dependencies.py"

    def test_when_fastapi_dependencies_present_then_audience_is_validated(self):
        """Criterion: `aud` claim is explicitly checked."""
        src = self._deps()
        assert "aud" in src, "Audience ('aud') check not present in dependencies.py"

    def test_when_fastapi_dependencies_present_then_issuer_is_validated(self):
        """Criterion: `iss` claim is explicitly checked (v2 issuer)."""
        src = self._deps()
        assert "iss" in src, "Issuer ('iss') check not present in dependencies.py"

    def test_when_fastapi_dependencies_present_then_tid_pinning_present(self):
        """Criterion: tenant ID (`tid`) is pinned."""
        src = self._deps()
        assert "tid" in src, "Tenant pinning ('tid') not found in dependencies.py"

    def test_when_fastapi_dependencies_present_then_scp_scope_enforced(self):
        """Criterion: required `scp` scope is enforced."""
        src = self._deps()
        assert "scp" in src, "Scope ('scp') enforcement not found in dependencies.py"

    def test_when_fastapi_dependencies_present_then_401_on_auth_failure(self):
        """Criterion: authentication failure raises HTTP 401."""
        src = self._deps()
        assert "401" in src or "HTTP_401" in src or "status.HTTP_401" in src, (
            "HTTP 401 response not found in dependencies.py"
        )

    def test_when_fastapi_dependencies_present_then_403_on_insufficient_scope(self):
        """Criterion: insufficient scope raises HTTP 403."""
        src = self._deps()
        assert "403" in src or "HTTP_403" in src or "status.HTTP_403" in src, (
            "HTTP 403 response not found in dependencies.py"
        )


# ---------------------------------------------------------------------------
# C2 — NestJS overlay: jsonwebtoken + jwks-rsa, tid, scp, 401/403
# ---------------------------------------------------------------------------


class TestNestjsOverlayJwtValidation:
    def _auth_service(self) -> str:
        candidates = list(
            (NESTJS_OVERLAY / "api" / "src").rglob("auth.service.ts")
        ) + list((NESTJS_OVERLAY / "api").rglob("auth.service.ts"))
        assert candidates, "auth.service.ts not found under templates-entra-nestjs/"
        return _read(candidates[0])

    def test_when_nestjs_overlay_present_then_jwks_rsa_in_package_json(self):
        """Criterion: JWKS resolution uses jwks-rsa (NestJS in-process)."""
        pkg = NESTJS_OVERLAY / "api" / "package.json"
        assert pkg.exists(), f"package.json not found at {pkg}"
        text = _read(pkg)
        assert "jwks-rsa" in text, "jwks-rsa not declared in entra-nestjs package.json"

    def test_when_nestjs_overlay_present_then_jsonwebtoken_in_package_json(self):
        """Criterion: signature validation uses jsonwebtoken."""
        pkg = NESTJS_OVERLAY / "api" / "package.json"
        assert pkg.exists(), f"package.json not found at {pkg}"
        text = _read(pkg)
        assert "jsonwebtoken" in text, (
            "jsonwebtoken not declared in entra-nestjs package.json"
        )

    def test_when_nestjs_auth_service_present_then_tid_pinning_present(self):
        """Criterion: tenant ID (`tid`) is pinned in NestJS auth service."""
        src = self._auth_service()
        assert "tid" in src, "Tenant pinning ('tid') not found in auth.service.ts"

    def test_when_nestjs_auth_service_present_then_scp_or_scope_enforced(self):
        """Criterion: required scope is enforced in NestJS auth service."""
        src = self._auth_service()
        assert "scp" in src or "scope" in src.lower(), (
            "Scope enforcement not found in auth.service.ts"
        )

    def test_when_nestjs_auth_service_present_then_401_on_auth_failure(self):
        """Criterion: authentication failure raises HTTP 401."""
        src = self._auth_service()
        assert "401" in src or "UnauthorizedException" in src, (
            "HTTP 401 / UnauthorizedException not found in auth.service.ts"
        )

    def test_when_nestjs_auth_service_present_then_403_on_insufficient_scope(self):
        """Criterion: insufficient scope raises HTTP 403."""
        src = self._auth_service()
        assert "403" in src or "ForbiddenException" in src, (
            "HTTP 403 / ForbiddenException not found in auth.service.ts"
        )


# ---------------------------------------------------------------------------
# C3 — No client secret in either backend
# ---------------------------------------------------------------------------

_CLIENT_SECRET_PATTERN = re.compile(
    r"client_secret|CLIENT_SECRET|clientSecret",
    re.IGNORECASE,
)

_BROWSER_SAFE_VARS = {
    "ENTRA_TENANT_ID",
    "ENTRA_SPA_CLIENT_ID",
}

_BACKEND_SECRET_SENSITIVE = re.compile(
    r"ENTRA_API_CLIENT_SECRET|client_secret", re.IGNORECASE
)


def test_when_fastapi_env_example_present_then_no_client_secret_key():
    """Criterion: FastAPI backend holds no client secret — .env.example must not declare one."""
    env_example = FASTAPI_OVERLAY / "api" / ".env.example"
    assert env_example.exists(), f".env.example not found at {env_example}"
    text = _read(env_example)
    assert not _BACKEND_SECRET_SENSITIVE.search(text), (
        "Client secret found in FastAPI .env.example — backend must be secret-free"
    )


def test_when_nestjs_env_example_present_then_no_client_secret_key():
    """Criterion: NestJS backend holds no client secret — .env.example must not declare one."""
    env_example = NESTJS_OVERLAY / "api" / ".env.example"
    assert env_example.exists(), f".env.example not found at {env_example}"
    text = _read(env_example)
    assert not _BACKEND_SECRET_SENSITIVE.search(text), (
        "Client secret found in NestJS .env.example — backend must be secret-free"
    )


def test_when_frontend_environment_ts_present_then_only_browser_safe_values():
    """
    Criterion: only browser-safe public values reach environment.ts.
    At minimum ENTRA_TENANT_ID and ENTRA_SPA_CLIENT_ID must be present;
    any client secret must NOT appear.
    """
    env_ts_candidates = list(FRONTEND_OVERLAY.rglob("environment.ts"))
    assert env_ts_candidates, "environment.ts not found under templates-entra-frontend/"
    text = _read(env_ts_candidates[0])
    for var in _BROWSER_SAFE_VARS:
        assert var in text, f"Browser-safe variable '{var}' missing from environment.ts"
    assert not _CLIENT_SECRET_PATTERN.search(text), (
        "Client secret detected in environment.ts — must not reach the frontend"
    )


# ---------------------------------------------------------------------------
# C4 — Overlay dirs mirror supabase layout; pyproject.toml + MANIFEST.in cover them
# ---------------------------------------------------------------------------


class TestOverlayLayoutMirrorsSupabase:
    """
    The criterion: three new overlays mirror supabase overlay layout 1:1 so copy_tree
    needs no special-casing.
    We verify each entra overlay contains at minimum the same top-level entry-point
    directories that the corresponding supabase overlay contains.
    """

    def _top_level_dirs(self, overlay: Path) -> set[str]:
        return {p.name for p in overlay.iterdir() if p.is_dir()}

    def test_when_entra_fastapi_overlay_exists_then_top_level_dirs_match_supabase(self):
        assert FASTAPI_OVERLAY.exists(), f"{FASTAPI_OVERLAY} does not exist"
        assert SUPABASE_FASTAPI_OVERLAY.exists(), (
            f"{SUPABASE_FASTAPI_OVERLAY} does not exist"
        )
        entra_dirs = self._top_level_dirs(FASTAPI_OVERLAY)
        supabase_dirs = self._top_level_dirs(SUPABASE_FASTAPI_OVERLAY)
        missing = supabase_dirs - entra_dirs
        assert not missing, (
            f"entra-fastapi overlay missing top-level dirs present in supabase-fastapi: {missing}"
        )

    def test_when_entra_nestjs_overlay_exists_then_top_level_dirs_match_supabase(self):
        assert NESTJS_OVERLAY.exists(), f"{NESTJS_OVERLAY} does not exist"
        assert SUPABASE_NESTJS_OVERLAY.exists(), (
            f"{SUPABASE_NESTJS_OVERLAY} does not exist"
        )
        entra_dirs = self._top_level_dirs(NESTJS_OVERLAY)
        supabase_dirs = self._top_level_dirs(SUPABASE_NESTJS_OVERLAY)
        missing = supabase_dirs - entra_dirs
        assert not missing, (
            f"entra-nestjs overlay missing top-level dirs present in supabase-nestjs: {missing}"
        )

    def test_when_entra_frontend_overlay_exists_then_top_level_dirs_match_supabase(
        self,
    ):
        assert FRONTEND_OVERLAY.exists(), f"{FRONTEND_OVERLAY} does not exist"
        assert SUPABASE_FRONTEND_OVERLAY.exists(), (
            f"{SUPABASE_FRONTEND_OVERLAY} does not exist"
        )
        entra_dirs = self._top_level_dirs(FRONTEND_OVERLAY)
        supabase_dirs = self._top_level_dirs(SUPABASE_FRONTEND_OVERLAY)
        missing = supabase_dirs - entra_dirs
        assert not missing, (
            f"entra-frontend overlay missing top-level dirs present in supabase-frontend: {missing}"
        )


class TestPackagingCoversAllThreeOverlays:
    def test_when_pyproject_toml_read_then_entra_fastapi_overlay_packaged(self):
        text = _read(PYPROJECT)
        assert "templates-entra-fastapi" in text, (
            "templates-entra-fastapi not declared in pyproject.toml package-data"
        )

    def test_when_pyproject_toml_read_then_entra_nestjs_overlay_packaged(self):
        text = _read(PYPROJECT)
        assert "templates-entra-nestjs" in text, (
            "templates-entra-nestjs not declared in pyproject.toml package-data"
        )

    def test_when_pyproject_toml_read_then_entra_frontend_overlay_packaged(self):
        text = _read(PYPROJECT)
        assert "templates-entra-frontend" in text, (
            "templates-entra-frontend not declared in pyproject.toml package-data"
        )

    def test_when_manifest_in_read_then_entra_fastapi_overlay_included(self):
        text = _read(MANIFEST)
        assert "templates-entra-fastapi" in text, (
            "templates-entra-fastapi not in MANIFEST.in recursive-include"
        )

    def test_when_manifest_in_read_then_entra_nestjs_overlay_included(self):
        text = _read(MANIFEST)
        assert "templates-entra-nestjs" in text, (
            "templates-entra-nestjs not in MANIFEST.in recursive-include"
        )

    def test_when_manifest_in_read_then_entra_frontend_overlay_included(self):
        text = _read(MANIFEST)
        assert "templates-entra-frontend" in text, (
            "templates-entra-frontend not in MANIFEST.in recursive-include"
        )


# ---------------------------------------------------------------------------
# C5 — JWKS auto-refresh; no hard-coded refresh schedule
# ---------------------------------------------------------------------------

_HARD_CODED_REFRESH = re.compile(
    r"(sleep|time\.sleep|setInterval|setTimeout)\s*\(",
    re.IGNORECASE,
)


def test_when_fastapi_overlay_present_then_pyjwks_client_used():
    """
    Criterion: FastAPI uses PyJWKClient (auto-refreshes on key rotation; no schedule).
    """
    deps_path = FASTAPI_OVERLAY / "api" / "app" / "api" / "deps.py"
    assert deps_path.exists(), f"dependencies.py not found at {deps_path}"
    src = _read(deps_path)
    assert "PyJWKClient" in src, "PyJWKClient not found in FastAPI dependencies.py"


def test_when_fastapi_overlay_present_then_no_hard_coded_refresh_schedule():
    """Criterion: no hard-coded refresh schedule (no sleep / setInterval)."""
    for py_file in FASTAPI_OVERLAY.rglob("*.py"):
        src = _read(py_file)
        assert not _HARD_CODED_REFRESH.search(src), (
            f"Hard-coded refresh schedule found in {py_file}"
        )


def test_when_nestjs_overlay_present_then_jwks_rsa_cache_enabled():
    """
    Criterion: NestJS uses jwks-rsa with cache:true and rateLimit:true.
    """
    candidates = list((NESTJS_OVERLAY / "api" / "src").rglob("auth.service.ts")) + list(
        (NESTJS_OVERLAY / "api").rglob("auth.service.ts")
    )
    assert candidates, "auth.service.ts not found under templates-entra-nestjs/"
    src = _read(candidates[0])
    assert "cache" in src and "true" in src, (
        "jwks-rsa cache:true not found in auth.service.ts"
    )
    assert "rateLimit" in src, "jwks-rsa rateLimit not found in auth.service.ts"


def test_when_nestjs_overlay_present_then_no_hard_coded_refresh_schedule():
    """Criterion: no hard-coded refresh schedule (no setInterval / setTimeout)."""
    for ts_file in NESTJS_OVERLAY.rglob("*.ts"):
        src = _read(ts_file)
        assert not _HARD_CODED_REFRESH.search(src), (
            f"Hard-coded refresh schedule found in {ts_file}"
        )


# ---------------------------------------------------------------------------
# Property-based: overlay dirs contain at least one file for every valid mode
# (invariant: adding new modes never results in empty overlay directories)
# ---------------------------------------------------------------------------


@given(
    st.sampled_from(
        [
            "templates-entra-fastapi",
            "templates-entra-nestjs",
            "templates-entra-frontend",
        ]
    )
)
def test_when_any_entra_overlay_dir_checked_then_it_contains_at_least_one_file(
    overlay_name,
):
    """
    Invariant (never-empty): every entra overlay directory packages real template
    files — an empty overlay would silently produce a broken scaffold.
    """
    overlay_dir = PKG_DIR / overlay_name
    assert overlay_dir.exists(), f"Overlay dir '{overlay_name}' does not exist"
    files = list(overlay_dir.rglob("*"))
    file_list = [f for f in files if f.is_file()]
    assert file_list, (
        f"Overlay dir '{overlay_name}' is empty — must contain template files"
    )
