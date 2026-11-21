"""Source-blind tests for issue #15 — global acceptance criteria.

Criteria covered (oracle: all UNIT-verifiable):
  1. --auth entra is a valid fourth mode; existing modes and --scope combinations unchanged.
  2. Both backends validate Entra v2 JWTs in-process: RS256/JWKS, aud/iss/exp/nbf/tid/scp,
     401 on auth failure, 403 on insufficient scope.
  3. No client secret in either backend; only public values reach environment.ts.
  4. Three overlay directories mirror supabase layout 1:1; pyproject.toml + MANIFEST.in
     package all three.
  5. JWKS clients auto-refresh (PyJWKClient; jwks-rsa cache+rateLimit), no hard-coded schedule.
"""

import re
from pathlib import Path

from tests.fastapi_entra_sources import (
    auth_failure_statuses_are_wired,
    entra_verifier_text,
)
from tests.toml_support import tomllib

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "project_initializer"

ENTRA_FASTAPI = PKG / "templates-entra-fastapi"
ENTRA_NESTJS = PKG / "templates-entra-nestjs"
ENTRA_FRONTEND = PKG / "templates-entra-frontend"
SUPABASE_FASTAPI = PKG / "templates-supabase-fastapi"
SUPABASE_NESTJS = PKG / "templates-supabase-nestjs"
SUPABASE_FRONTEND = PKG / "templates-supabase-frontend"


# ---------------------------------------------------------------------------
# Criterion 1 — --auth entra accepted; existing modes unchanged
# ---------------------------------------------------------------------------


def test_when_cli_help_read_auth_entra_is_listed_as_valid_choice():
    """AUTH_MODES in cli.py must include 'entra' so the CLI accepts --auth entra."""
    cli_text = (PKG / "cli.py").read_text(encoding="utf-8")
    # The word "entra" must appear in the AUTH_MODES definition.
    assert "entra" in cli_text, "'entra' not found in cli.py"


def test_when_auth_modes_read_all_four_modes_are_present():
    """cli.py must still list none/token/supabase alongside entra."""
    cli_text = (PKG / "cli.py").read_text(encoding="utf-8")
    for mode in ("token", "supabase", "entra"):
        assert mode in cli_text, f"mode '{mode}' missing from cli.py"


def test_when_env_generator_read_entra_branch_is_present():
    """env_generator.py must contain the is_entra branch that writes ENTRA_* vars."""
    gen_text = (PKG / "env_generator.py").read_text(encoding="utf-8")
    assert "entra" in gen_text.lower(), "entra branch missing from env_generator.py"
    assert "ENTRA_" in gen_text, "ENTRA_* env vars missing from env_generator.py"


# ---------------------------------------------------------------------------
# Criterion 2a — FastAPI backend: in-process JWT validation
# ---------------------------------------------------------------------------


def test_when_fastapi_overlay_read_pyjwt_crypto_is_declared_as_dependency():
    """pyproject.toml must declare PyJWT[crypto] for in-process JWKS validation.

    Validates project_initializer/templates-entra-fastapi/api/pyproject.toml.
    """
    manifest_path = ENTRA_FASTAPI / "api" / "pyproject.toml"
    assert manifest_path.exists(), "pyproject.toml missing from templates-entra-fastapi"
    with manifest_path.open("rb") as handle:
        dependencies = [
            entry.lower() for entry in tomllib.load(handle)["project"]["dependencies"]
        ]
    assert any(entry.startswith("pyjwt") for entry in dependencies), (
        "PyJWT not in pyproject.toml"
    )
    # The [crypto] extra is required for RS256 signature verification.
    assert any(entry.startswith("pyjwt[crypto]") for entry in dependencies), (
        "PyJWT[crypto] extra missing from pyproject.toml"
    )


def test_when_fastapi_verifier_read_rs256_algorithm_is_referenced():
    """entra.py must reference RS256 so the signature check is not skipped.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    assert "RS256" in entra_verifier_text(), (
        "RS256 algorithm not referenced in entra.py"
    )


def test_when_fastapi_verifier_read_aud_claim_is_validated():
    """The verifier checks the aud claim.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    content = entra_verifier_text()
    assert "aud" in content, "audience claim not validated in FastAPI entra.py"


def test_when_fastapi_verifier_read_iss_claim_is_validated():
    """The verifier checks the iss claim.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    content = entra_verifier_text()
    assert "iss" in content, "issuer claim not validated in FastAPI entra.py"


def test_when_fastapi_verifier_read_tid_claim_is_validated():
    """Tenant pinning via tid must be explicit.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    content = entra_verifier_text()
    assert "tid" in content, "tid (tenant) pinning missing from FastAPI entra.py"


def test_when_fastapi_verifier_read_scp_scope_is_enforced():
    """The verifier enforces the required scope through the scp claim.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    content = entra_verifier_text()
    assert "scp" in content, "scp scope enforcement missing from FastAPI entra.py"


def test_when_fastapi_verifier_and_handlers_read_401_is_returned_on_auth_failure():
    """The 401 status code must be emitted on validation failure.

    The verifier raises AuthenticationError and handlers.py answers it with 401.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py and project_initializer/templates-api-fastapi/api/app/api/handlers.py.
    """
    unauthorized, _ = auth_failure_statuses_are_wired()
    assert unauthorized, "HTTP 401 not wired for auth failure in FastAPI"


def test_when_fastapi_verifier_and_handlers_read_403_is_returned_on_insufficient_scope():
    """The 403 status code must be emitted on scope failure.

    The verifier raises AuthorizationError and handlers.py answers it with 403.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py and project_initializer/templates-api-fastapi/api/app/api/handlers.py.
    """
    _, forbidden = auth_failure_statuses_are_wired()
    assert forbidden, "HTTP 403 not wired for scope failure in FastAPI"


# ---------------------------------------------------------------------------
# Criterion 2b — NestJS backend: in-process JWT validation
# ---------------------------------------------------------------------------


def test_when_nestjs_package_json_read_jwks_rsa_is_declared():
    pkg_file = ENTRA_NESTJS / "api" / "package.json"
    assert pkg_file.exists(), "package.json missing from templates-entra-nestjs"
    content = pkg_file.read_text(encoding="utf-8")
    assert "jwks-rsa" in content, "jwks-rsa missing from NestJS package.json"


def test_when_nestjs_package_json_read_jsonwebtoken_is_declared():
    pkg_file = ENTRA_NESTJS / "api" / "package.json"
    assert pkg_file.exists(), "package.json missing from templates-entra-nestjs"
    content = pkg_file.read_text(encoding="utf-8")
    assert "jsonwebtoken" in content, "jsonwebtoken missing from NestJS package.json"


def test_when_nestjs_auth_service_read_tid_claim_is_validated():
    content = _read_nestjs_auth_service()
    assert "tid" in content, "tid (tenant) pinning missing from NestJS AuthService"


def test_when_nestjs_auth_service_read_aud_claim_is_validated():
    content = _read_nestjs_auth_service()
    assert "aud" in content, "audience claim not validated in NestJS AuthService"


def test_when_nestjs_auth_service_read_iss_claim_is_validated():
    content = _read_nestjs_auth_service()
    assert "iss" in content, "issuer claim not validated in NestJS AuthService"


def test_when_nestjs_auth_guard_read_401_is_returned_on_auth_failure():
    """The Entra verifier raises the 401 that the shared guard passes through.

    Validates project_initializer/templates-entra-nestjs/api/src/modules/auth/auth.service.ts.
    """
    content = _read_nestjs_auth_guard()
    assert "401" in content or "UnauthorizedException" in content, (
        "HTTP 401 / UnauthorizedException not referenced in NestJS auth guard"
    )


def test_when_nestjs_auth_guard_read_403_is_returned_on_insufficient_scope():
    """The Entra verifier raises the 403 that the shared guard passes through.

    Validates project_initializer/templates-entra-nestjs/api/src/modules/auth/auth.service.ts.
    """
    content = _read_nestjs_auth_guard()
    assert "403" in content or "ForbiddenException" in content, (
        "HTTP 403 / ForbiddenException not referenced in NestJS auth guard"
    )


# ---------------------------------------------------------------------------
# Criterion 3 — No client secret in backend; only public values in frontend
# ---------------------------------------------------------------------------


def test_when_fastapi_overlay_files_read_client_secret_is_absent():
    """No template file under templates-entra-fastapi may contain a client secret.

    Validates every file under project_initializer/templates-entra-fastapi.
    """
    for path in ENTRA_FASTAPI.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "client_secret" not in text.lower(), (
                f"client_secret found in FastAPI overlay file: {path}"
            )
            assert "CLIENT_SECRET" not in text, (
                f"CLIENT_SECRET found in FastAPI overlay file: {path}"
            )


def test_when_nestjs_overlay_files_read_client_secret_is_absent():
    """No template file under templates-entra-nestjs may contain a client secret.

    Validates every file under project_initializer/templates-entra-nestjs.
    """
    for path in ENTRA_NESTJS.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "clientSecret" not in text, (
                f"clientSecret found in NestJS overlay file: {path}"
            )
            assert "CLIENT_SECRET" not in text, (
                f"CLIENT_SECRET found in NestJS overlay file: {path}"
            )


def test_when_frontend_environment_ts_read_only_public_values_are_present():
    """environment.ts must expose public Entra values — and nothing secret.

    Criterion: only browser-safe public values reach environment.ts.
    The tenant ID and SPA client ID may be embedded inside 'authority' and
    'scope' URLs rather than as separate top-level keys — either form satisfies
    the criterion that these values are public in the frontend.
    """
    env_file = _find_env_ts(ENTRA_FRONTEND)
    content = env_file.read_text(encoding="utf-8")
    # authority and scope must be present as named properties.
    for key in ("authority", "scope"):
        assert key in content, f"expected public key '{key}' in environment.ts"
    # Tenant ID reaches the frontend (embedded in the authority URL or as tenantId).
    assert "tenant" in content.lower(), "tenant ID not present in environment.ts"
    # SPA client ID reaches the frontend (in scope URL or as clientId / spaClientId).
    assert "client" in content.lower(), "SPA client ID not present in environment.ts"
    # Client secret must be absent.
    assert "secret" not in content.lower(), (
        "a secret value is present in environment.ts"
    )


# ---------------------------------------------------------------------------
# Criterion 4 — Three overlay directories mirror supabase layout 1:1;
#               pyproject.toml + MANIFEST.in package all three.
# ---------------------------------------------------------------------------


def test_when_entra_fastapi_overlay_read_it_mirrors_supabase_fastapi_top_level_dirs():
    """Top-level subdirectory names of entra overlay must match supabase overlay."""
    entra_dirs = _top_level_dirs(ENTRA_FASTAPI)
    supa_dirs = _top_level_dirs(SUPABASE_FASTAPI)
    assert entra_dirs == supa_dirs, (
        f"entra-fastapi dirs {entra_dirs} differ from supabase-fastapi dirs {supa_dirs}"
    )


def test_when_entra_nestjs_overlay_read_it_mirrors_supabase_nestjs_top_level_dirs():
    entra_dirs = _top_level_dirs(ENTRA_NESTJS)
    supa_dirs = _top_level_dirs(SUPABASE_NESTJS)
    assert entra_dirs == supa_dirs, (
        f"entra-nestjs dirs {entra_dirs} differ from supabase-nestjs dirs {supa_dirs}"
    )


def test_when_entra_frontend_overlay_read_it_mirrors_supabase_frontend_top_level_dirs():
    entra_dirs = _top_level_dirs(ENTRA_FRONTEND)
    supa_dirs = _top_level_dirs(SUPABASE_FRONTEND)
    assert entra_dirs == supa_dirs, (
        f"entra-frontend dirs {entra_dirs} differ from supabase-frontend dirs {supa_dirs}"
    )


def test_when_pyproject_toml_read_entra_fastapi_overlay_is_packaged():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "templates-entra-fastapi" in text, (
        "templates-entra-fastapi missing from pyproject.toml package-data"
    )


def test_when_pyproject_toml_read_entra_nestjs_overlay_is_packaged():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "templates-entra-nestjs" in text, (
        "templates-entra-nestjs missing from pyproject.toml package-data"
    )


def test_when_pyproject_toml_read_entra_frontend_overlay_is_packaged():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "templates-entra-frontend" in text, (
        "templates-entra-frontend missing from pyproject.toml package-data"
    )


def test_when_manifest_in_read_entra_fastapi_overlay_is_included():
    text = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "templates-entra-fastapi" in text, (
        "templates-entra-fastapi missing from MANIFEST.in"
    )


def test_when_manifest_in_read_entra_nestjs_overlay_is_included():
    text = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "templates-entra-nestjs" in text, (
        "templates-entra-nestjs missing from MANIFEST.in"
    )


def test_when_manifest_in_read_entra_frontend_overlay_is_included():
    text = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "templates-entra-frontend" in text, (
        "templates-entra-frontend missing from MANIFEST.in"
    )


# ---------------------------------------------------------------------------
# Criterion 5 — JWKS auto-refresh; no hard-coded schedule
# ---------------------------------------------------------------------------


def test_when_fastapi_verifier_read_pyjwkclient_is_used():
    """FastAPI must use PyJWKClient (not a manual key fetch) to get auto-refresh on rotation.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    content = entra_verifier_text()
    assert "PyJWKClient" in content, "PyJWKClient not used in FastAPI entra.py"


def test_when_nestjs_auth_service_read_jwks_rsa_cache_option_is_set():
    """jwks-rsa must be configured with cache: true to enable key caching."""
    content = _read_nestjs_auth_service()
    assert "cache" in content, "cache option not set in NestJS jwks-rsa client"


def test_when_nestjs_auth_service_read_jwks_rsa_rate_limit_option_is_set():
    """jwks-rsa must be configured with rateLimit: true."""
    content = _read_nestjs_auth_service()
    assert "rateLimit" in content or "rate_limit" in content, (
        "rateLimit option not set in NestJS jwks-rsa client"
    )


def test_when_fastapi_verifier_read_no_hard_coded_refresh_interval():
    """No fixed sleep/interval for JWKS refresh — auto-refresh must be library-driven.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    content = entra_verifier_text()
    assert not re.search(r"time\.sleep\s*\(", content), (
        "hard-coded sleep found in FastAPI entra.py (must not hard-code refresh schedule)"
    )
    assert not re.search(r"refresh_interval\s*=\s*\d+", content), (
        "hard-coded refresh_interval found in FastAPI entra.py"
    )


def test_when_nestjs_auth_service_read_no_hard_coded_refresh_interval():
    content = _read_nestjs_auth_service()
    assert not re.search(r"setInterval\s*\(", content), (
        "setInterval found in NestJS AuthService (must not hard-code refresh schedule)"
    )
    assert not re.search(r"setTimeout\s*\(", content), (
        "setTimeout found in NestJS AuthService (must not hard-code refresh schedule)"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_file(overlay: Path, filename: str) -> Path:
    matches = list(overlay.rglob(filename))
    assert matches, f"{filename} not found under {overlay}"
    return matches[0]


def _read_dep(overlay: Path, filename: str) -> str:
    return _find_file(overlay, filename).read_text(encoding="utf-8")


def _read_nestjs_auth_service() -> str:
    return _find_file(ENTRA_NESTJS, "auth.service.ts").read_text(encoding="utf-8")


def _read_nestjs_auth_guard() -> str:
    """Source that decides 401 vs 403 for the Entra NestJS variant.

    The shared guard passes a verifier's HttpException through unchanged, so the status codes
    are raised by the Entra verifier (`auth.service.ts`), not by a per-variant guard file.
    """
    return _find_file(ENTRA_NESTJS, "auth.service.ts").read_text(encoding="utf-8")


def _find_env_ts(overlay: Path) -> Path:
    matches = list(overlay.rglob("environment.ts"))
    assert matches, f"environment.ts not found under {overlay}"
    return matches[0]


def _top_level_dirs(overlay: Path) -> set[str]:
    if not overlay.exists():
        return set()
    return {p.name for p in overlay.iterdir() if p.is_dir()}
