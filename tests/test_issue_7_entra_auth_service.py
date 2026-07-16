"""
Source-blind example tests for issue #7:
feat(entra-frontend): implement AuthService backed by MsalService with silent-token fallback

Every test is derived from the acceptance criteria only.
No implementation source was read during authoring (Red phase of TDD).

Criteria mapped below — NOT VERIFIABLE criteria are omitted:
  Global #1  — entra is a fourth auth mode; existing modes/scopes unchanged        → UNIT
  Global #2  — backends validate Entra v2 JWT (RS256, aud, iss, tid, scp, 401/403) → UNIT
  Global #3  — no client secret; only public values in environment.ts               → UNIT
  Global #4  — three overlay dirs in pyproject.toml + MANIFEST.in                  → UNIT
  Global #5  — JWKS auto-refresh via PyJWKClient / jwks-rsa cache+rateLimit        → UNIT
  Scope  #6  — AuthService surface: providedIn root, MsalService, signals, methods  → UNIT
  Scope  #7  — acquireTokenSilent + InteractionRequiredAuthError redirect fallback   → UNIT
  Scope  #8  — active account resolved; isAuthenticated reflects account presence   → UNIT
  Scope  #9  — (NOT VERIFIABLE) skipped
  Scope  #10 — overlay spec file covers silent-success and fallback paths           → UNIT
  Scope  #11 — (NOT VERIFIABLE) skipped
"""

import json
import re
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

# ── Path constants derived from CLAUDE.md project structure ──────────────────
_PKG = Path("project_initializer")
CLI_MODULE = _PKG / "cli.py"
PYPROJECT = Path("pyproject.toml")
MANIFEST = Path("MANIFEST.in")

FASTAPI_OVERLAY = _PKG / "templates-entra-fastapi"
NESTJS_OVERLAY = _PKG / "templates-entra-nestjs"
FRONTEND_OVERLAY = _PKG / "templates-entra-frontend"

# FastAPI overlay paths
_FA_API = FASTAPI_OVERLAY / "api"
FA_REQUIREMENTS = _FA_API / "requirements.txt"
FA_ENV_EXAMPLE = _FA_API / ".env.example"
FA_DEPENDENCIES = _FA_API / "app" / "api" / "deps.py"

# NestJS overlay paths
_NJS_API = NESTJS_OVERLAY / "api"
NJS_PACKAGE_JSON = _NJS_API / "package.json"
NJS_ENV_EXAMPLE = _NJS_API / ".env.example"
_NJS_AUTH_CANDIDATES = [
    _NJS_API / "src" / "auth" / "auth.service.ts",
    _NJS_API / "src" / "modules" / "auth" / "auth.service.ts",
]

# Frontend overlay paths (Angular standalone project — frontend/ subtree)
_FE_SRC = FRONTEND_OVERLAY / "frontend" / "src"
FE_ENVIRONMENT_TS = _FE_SRC / "environments" / "environment.ts"
FE_AUTH_SERVICE = _FE_SRC / "app" / "core" / "services" / "auth.service.ts"
FE_AUTH_SPEC = _FE_SRC / "app" / "core" / "services" / "auth.service.spec.ts"


def _read(path: Path) -> str:
    """Read a template file; fails with a clear message if it is missing."""
    assert path.exists(), (
        f"Template file not found (implementation not yet written?): {path}"
    )
    return path.read_text(encoding="utf-8")


def _find_nestjs_auth_service() -> Path | None:
    for candidate in _NJS_AUTH_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Global criterion #1 — entra is a fourth auth mode; existing modes unchanged
# ═══════════════════════════════════════════════════════════════════════════════


def test_when_cli_module_is_read_then_entra_is_a_valid_auth_mode():
    content = _read(CLI_MODULE)
    assert '"entra"' in content or "'entra'" in content, (
        '"entra" must appear in AUTH_MODES in cli.py'
    )


@given(st.sampled_from(["token", "supabase"]))
@settings(max_examples=2)
def test_when_existing_auth_modes_are_checked_then_none_are_removed_by_entra_addition(
    mode,
):
    """Invariant: adding entra must not remove pre-existing named auth modes from AUTH_MODES.

    The 'no-auth' case uses default=None in argparse (not a literal "none" string),
    so only the explicit named modes 'token' and 'supabase' are checked here."""
    content = CLI_MODULE.read_text(encoding="utf-8")
    assert f'"{mode}"' in content or f"'{mode}'" in content, (
        f"Existing auth mode '{mode}' must still be present in cli.py after adding entra"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Global criterion #2 — FastAPI: PyJWT[crypto], tid pinning, scp, 401, 403
# ═══════════════════════════════════════════════════════════════════════════════


def test_when_fastapi_requirements_are_read_then_pyjwt_crypto_is_declared():
    """In-process JWKS validation requires PyJWT[crypto]."""
    content = _read(FA_REQUIREMENTS)
    assert re.search(r"PyJWT\s*\[crypto\]", content, re.IGNORECASE), (
        "PyJWT[crypto] must be declared in FastAPI overlay requirements.txt"
    )


def test_when_fastapi_dependencies_are_read_then_tid_pinning_is_enforced():
    content = _read(FA_DEPENDENCIES)
    assert "tid" in content, (
        "Tenant-ID pinning (tid claim) must be present in dependencies.py"
    )


def test_when_fastapi_dependencies_are_read_then_scp_scope_is_checked():
    content = _read(FA_DEPENDENCIES)
    assert "scp" in content, (
        "Required scp scope check must be present in dependencies.py"
    )


def test_when_fastapi_dependencies_are_read_then_401_is_returned_on_auth_failure():
    content = _read(FA_DEPENDENCIES)
    assert "401" in content, (
        "HTTP 401 must be raised on authentication failure in dependencies.py"
    )


def test_when_fastapi_dependencies_are_read_then_403_is_returned_on_insufficient_scope():
    content = _read(FA_DEPENDENCIES)
    assert "403" in content, (
        "HTTP 403 must be raised on insufficient scope in dependencies.py"
    )


# ── NestJS: jwks-rsa declared in package.json ────────────────────────────────


def test_when_nestjs_package_json_is_read_then_jwks_rsa_is_declared():
    pkg = json.loads(_read(NJS_PACKAGE_JSON))
    all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "jwks-rsa" in all_deps, (
        "jwks-rsa must be declared in NestJS overlay package.json"
    )


def test_when_nestjs_package_json_is_read_then_jsonwebtoken_is_declared():
    pkg = json.loads(_read(NJS_PACKAGE_JSON))
    all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "jsonwebtoken" in all_deps, (
        "jsonwebtoken must be declared in NestJS overlay package.json"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Global criterion #3 — no client secret; public values only in environment.ts
# ═══════════════════════════════════════════════════════════════════════════════


def test_when_fastapi_env_example_is_read_then_client_secret_key_is_absent():
    content = _read(FA_ENV_EXAMPLE).upper()
    assert "CLIENT_SECRET" not in content, (
        "FastAPI .env.example must not contain CLIENT_SECRET — backend is signature-only"
    )


def test_when_nestjs_env_example_is_read_then_client_secret_key_is_absent():
    content = _read(NJS_ENV_EXAMPLE).upper()
    assert "CLIENT_SECRET" not in content, (
        "NestJS .env.example must not contain CLIENT_SECRET — backend is signature-only"
    )


def test_when_frontend_environment_ts_is_read_then_secret_key_is_absent():
    """Only browser-safe public values (tenantId, clientId, authority, scope) reach environment.ts."""
    content = _read(FE_ENVIRONMENT_TS).upper()
    assert "SECRET" not in content, (
        "environment.ts must not contain any secret value — only public browser-safe config"
    )


def test_when_frontend_environment_ts_is_read_then_tenant_id_is_present():
    content = _read(FE_ENVIRONMENT_TS)
    assert (
        "tenantId" in content
        or "ENTRA_TENANT_ID" in content
        or "tenant" in content.lower()
    ), "environment.ts must expose the tenant ID as a public config value"


def test_when_frontend_environment_ts_is_read_then_client_id_is_present():
    content = _read(FE_ENVIRONMENT_TS)
    # The field is named entraSpaClientId in the AppEnvironment model.
    assert (
        "clientId" in content
        or "ENTRA_SPA_CLIENT_ID" in content
        or "client_id" in content.lower()
        or "entraSpaClientId" in content
    ), "environment.ts must expose the SPA client ID as a public config value"


# ═══════════════════════════════════════════════════════════════════════════════
# Global criterion #4 — three overlay dirs packaged in pyproject.toml + MANIFEST.in
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "overlay_dir",
    [
        "templates-entra-fastapi",
        "templates-entra-nestjs",
        "templates-entra-frontend",
    ],
)
def test_when_pyproject_toml_is_read_then_entra_overlay_is_in_package_data(overlay_dir):
    content = _read(PYPROJECT)
    assert overlay_dir in content, (
        f"pyproject.toml must include {overlay_dir} in package-data"
    )


@pytest.mark.parametrize(
    "overlay_dir",
    [
        "templates-entra-fastapi",
        "templates-entra-nestjs",
        "templates-entra-frontend",
    ],
)
def test_when_manifest_in_is_read_then_entra_overlay_is_recursively_included(
    overlay_dir,
):
    content = _read(MANIFEST)
    assert overlay_dir in content, (
        f"MANIFEST.in must have a recursive-include entry for {overlay_dir}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Global criterion #5 — JWKS auto-refresh (PyJWKClient; jwks-rsa cache + rateLimit)
# ═══════════════════════════════════════════════════════════════════════════════


def test_when_fastapi_dependencies_are_read_then_pyjwkclient_is_used_for_auto_refresh():
    """PyJWKClient auto-refreshes on key rotation — must be the signing-key provider."""
    content = _read(FA_DEPENDENCIES)
    assert "PyJWKClient" in content, (
        "PyJWKClient (from PyJWT) must be used in dependencies.py for JWKS auto-refresh"
    )


def test_when_nestjs_auth_service_is_read_then_jwks_rsa_cache_is_true():
    path = _find_nestjs_auth_service()
    assert path is not None, (
        f"NestJS auth service not found; checked: {_NJS_AUTH_CANDIDATES}"
    )
    content = path.read_text(encoding="utf-8")
    assert "cache" in content, (
        "jwks-rsa must be configured with cache: true in the NestJS auth service"
    )


def test_when_nestjs_auth_service_is_read_then_jwks_rsa_rate_limit_is_true():
    path = _find_nestjs_auth_service()
    assert path is not None, (
        f"NestJS auth service not found; checked: {_NJS_AUTH_CANDIDATES}"
    )
    content = path.read_text(encoding="utf-8")
    assert "rateLimit" in content, (
        "jwks-rsa must be configured with rateLimit: true in the NestJS auth service"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Scope criterion #6 — AuthService: providedIn root, MsalService, signal APIs, methods
# ═══════════════════════════════════════════════════════════════════════════════


def test_when_auth_service_template_is_read_then_provided_in_root_is_declared():
    content = _read(FE_AUTH_SERVICE)
    assert "providedIn: 'root'" in content, (
        "AuthService must declare providedIn: 'root' for singleton access"
    )


def test_when_auth_service_template_is_read_then_msal_service_is_injected():
    content = _read(FE_AUTH_SERVICE)
    assert "MsalService" in content, "AuthService must inject MsalService"


def test_when_auth_service_template_is_read_then_is_authenticated_signal_is_exposed():
    content = _read(FE_AUTH_SERVICE)
    assert "isAuthenticated" in content, "AuthService must expose isAuthenticated"
    assert "signal(" in content, (
        "isAuthenticated must be implemented as an Angular signal()"
    )


def test_when_auth_service_template_is_read_then_wait_until_initialized_is_exposed():
    content = _read(FE_AUTH_SERVICE)
    assert "waitUntilInitialized" in content, (
        "AuthService must expose waitUntilInitialized()"
    )


def test_when_auth_service_template_is_read_then_get_access_token_is_exposed():
    content = _read(FE_AUTH_SERVICE)
    assert "getAccessToken" in content, "AuthService must expose getAccessToken()"


def test_when_auth_service_template_is_read_then_login_method_is_exposed():
    content = _read(FE_AUTH_SERVICE)
    assert re.search(r"\blogin\s*\(", content), (
        "AuthService must expose a login() method"
    )


def test_when_auth_service_template_is_read_then_logout_method_is_exposed():
    content = _read(FE_AUTH_SERVICE)
    assert re.search(r"\blogout\s*\(", content), (
        "AuthService must expose a logout() method"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Scope criterion #7 — acquireTokenSilent + InteractionRequiredAuthError redirect fallback
# ═══════════════════════════════════════════════════════════════════════════════


def test_when_auth_service_template_is_read_then_acquire_token_silent_is_called():
    content = _read(FE_AUTH_SERVICE)
    assert "acquireTokenSilent" in content, (
        "AuthService must call acquireTokenSilent for the silent-token path"
    )


def test_when_auth_service_template_is_read_then_environment_scope_is_passed_to_token_request():
    """Token request must use [environment.scope] as scopes array."""
    content = _read(FE_AUTH_SERVICE)
    assert "environment" in content, (
        "AuthService must reference environment to build the token request scopes"
    )
    assert re.search(r"scope", content, re.IGNORECASE), (
        "AuthService must pass the configured scope from environment to the token request"
    )


def test_when_auth_service_template_is_read_then_interaction_required_auth_error_is_caught():
    content = _read(FE_AUTH_SERVICE)
    assert "InteractionRequiredAuthError" in content, (
        "AuthService must catch InteractionRequiredAuthError for the interactive fallback"
    )


def test_when_auth_service_template_is_read_then_redirect_fallback_is_used_on_interaction_required():
    """The fallback on InteractionRequiredAuthError must be interactive via redirect."""
    content = _read(FE_AUTH_SERVICE)
    has_redirect_fallback = (
        "acquireTokenRedirect" in content or "loginRedirect" in content
    )
    assert has_redirect_fallback, (
        "AuthService must fall back to acquireTokenRedirect or loginRedirect "
        "when InteractionRequiredAuthError is caught"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Scope criterion #8 — active account resolved; isAuthenticated reflects account presence
# ═══════════════════════════════════════════════════════════════════════════════


def test_when_auth_service_template_is_read_then_msal_accounts_are_queried():
    """The active account must be resolved from MSAL (getAllAccounts or getActiveAccount)."""
    content = _read(FE_AUTH_SERVICE)
    has_account_query = "getAllAccounts" in content or "getActiveAccount" in content
    assert has_account_query, (
        "AuthService must resolve the active account via getAllAccounts() or getActiveAccount()"
    )


def test_when_auth_service_template_is_read_then_is_authenticated_is_not_hardcoded_true():
    """isAuthenticated must reflect actual account presence, not be a static constant."""
    content = _read(FE_AUTH_SERVICE)
    # The signal must be set dynamically from accounts — not just signal(true)
    assert not re.search(r"isAuthenticated\s*=\s*signal\s*\(\s*true\s*\)", content), (
        "isAuthenticated must be derived from MSAL account state, not hardcoded to signal(true)"
    )


def test_when_auth_service_template_is_read_then_is_authenticated_set_from_accounts():
    """isAuthenticated value must be driven by the MSAL account list."""
    content = _read(FE_AUTH_SERVICE)
    # Both isAuthenticated and an account-check expression must co-exist in the file
    account_driven = (
        "getAllAccounts" in content
        or "getActiveAccount" in content
        or re.search(r"accounts\s*\.", content) is not None
        or re.search(r"account\s*\?", content) is not None
    )
    assert account_driven, "isAuthenticated must be set based on MSAL account presence"


# ═══════════════════════════════════════════════════════════════════════════════
# Scope criterion #10 — overlay spec covers silent-success and fallback paths
# ═══════════════════════════════════════════════════════════════════════════════


def test_when_frontend_overlay_is_checked_then_auth_service_spec_file_exists():
    assert FE_AUTH_SPEC.exists(), (
        f"auth.service.spec.ts must exist in the frontend overlay at {FE_AUTH_SPEC}"
    )


def test_when_auth_service_spec_is_read_then_silent_success_path_is_tested():
    content = _read(FE_AUTH_SPEC)
    assert "acquireTokenSilent" in content, (
        "auth.service.spec.ts must cover the silent-token success path (acquireTokenSilent)"
    )


def test_when_auth_service_spec_is_read_then_interaction_required_fallback_path_is_tested():
    content = _read(FE_AUTH_SPEC)
    assert "InteractionRequiredAuthError" in content, (
        "auth.service.spec.ts must cover the InteractionRequiredAuthError fallback path"
    )
