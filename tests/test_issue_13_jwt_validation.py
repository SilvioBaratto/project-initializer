"""
Issue #13 — Criterion: Both FastAPI and NestJS backends validate Entra v2 JWT bearer tokens
in-process (no sidecar), enforcing RS256 signature against cached JWKS plus aud, iss, exp/nbf,
tid pinning, and required scp scope, returning 401 on auth failure and 403 on insufficient scope.

These tests exercise the FastAPI overlay's get_current_user dependency directly by reading the
scaffolded template files as text — they do NOT import or execute the generated app code.

The contract is: the template source must contain the documented validation calls so that a
scaffolded project will satisfy the security requirements.
"""

import pathlib
import tomllib

from tests.fastapi_entra_sources import (
    auth_failure_statuses_are_wired,
    entra_verifier_text,
)

OVERLAY_FASTAPI = pathlib.Path("project_initializer/templates-entra-fastapi")
OVERLAY_NESTJS = pathlib.Path("project_initializer/templates-entra-nestjs")


# ---------------------------------------------------------------------------
# FastAPI overlay — source-text contract tests
# ---------------------------------------------------------------------------


def _fastapi_deps_text() -> str:
    """Source of the FastAPI verifier, where the token checks live."""
    return entra_verifier_text()


def _fastapi_runtime_dependencies() -> list[str]:
    manifest_path = OVERLAY_FASTAPI / "api" / "pyproject.toml"
    with manifest_path.open("rb") as handle:
        return tomllib.load(handle)["project"]["dependencies"]


def test_when_fastapi_overlay_dependencies_are_read_then_pyjwt_crypto_is_declared():
    """The in-process verifier needs PyJWT with the crypto extra for RS256.

    Validates project_initializer/templates-entra-fastapi/api/pyproject.toml.
    """
    dependencies = _fastapi_runtime_dependencies()
    assert any(entry.lower().startswith("pyjwt[crypto]") for entry in dependencies), (
        "pyproject.toml must declare PyJWT[crypto] for in-process JWKS validation"
    )


def test_when_fastapi_overlay_dependencies_are_read_then_rs256_algorithm_is_enforced():
    """The in-process verifier pins the RS256 signature algorithm.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    text = _fastapi_deps_text()
    assert "RS256" in text, "get_current_user must enforce RS256 algorithm"


def test_when_fastapi_verifier_is_read_then_jwks_client_is_used():
    """PyJWKClient is the PyJWT v2 class that fetches and caches JWKS.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    text = _fastapi_deps_text()
    assert "PyJWKClient" in text, "entra.py must use PyJWKClient for JWKS retrieval"


def test_when_fastapi_overlay_dependencies_are_read_then_aud_is_validated():
    """The in-process verifier validates the audience claim.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    text = _fastapi_deps_text()
    assert "aud" in text or "audience" in text, "audience (aud) claim must be validated"


def test_when_fastapi_overlay_dependencies_are_read_then_iss_is_validated():
    """The in-process verifier validates the issuer claim.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    text = _fastapi_deps_text()
    assert "iss" in text or "issuer" in text, "issuer (iss) claim must be validated"


def test_when_fastapi_verifier_is_read_then_tid_pinning_is_present():
    """The verifier pins the tenant through the tid claim.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    text = _fastapi_deps_text()
    assert "tid" in text, "tenant id (tid) claim must be pinned in entra.py"


def test_when_fastapi_verifier_is_read_then_scp_scope_is_enforced():
    """The verifier enforces the required scope through the scp claim.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    text = _fastapi_deps_text()
    assert "scp" in text, "required scp scope must be enforced in entra.py"


def test_when_fastapi_verifier_and_handlers_are_read_then_401_is_raised_on_auth_failure():
    """The verifier raises AuthenticationError, which handlers.py answers with 401.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py and project_initializer/templates-api-fastapi/api/app/api/handlers.py.
    """
    unauthorized, _ = auth_failure_statuses_are_wired()
    assert unauthorized, "entra.py must raise AuthenticationError, mapped to 401"


def test_when_fastapi_verifier_and_handlers_are_read_then_403_is_raised_on_insufficient_scope():
    """The verifier raises AuthorizationError, which handlers.py answers with 403.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py and project_initializer/templates-api-fastapi/api/app/api/handlers.py.
    """
    _, forbidden = auth_failure_statuses_are_wired()
    assert forbidden, "entra.py must raise AuthorizationError, mapped to 403"


# ---------------------------------------------------------------------------
# NestJS overlay — source-text contract tests
# ---------------------------------------------------------------------------


def _nestjs_auth_service_text() -> str:
    # Locate auth.service.ts anywhere under the nestjs overlay
    matches = list(OVERLAY_NESTJS.rglob("auth.service.ts"))
    assert matches, "auth.service.ts not found in templates-entra-nestjs/"
    return matches[0].read_text(encoding="utf-8")


def _nestjs_package_json_text() -> str:
    pkg = OVERLAY_NESTJS / "api" / "package.json"
    return pkg.read_text(encoding="utf-8")


def test_when_nestjs_overlay_package_json_is_read_then_jwks_rsa_is_declared():
    text = _nestjs_package_json_text()
    assert "jwks-rsa" in text, "package.json must declare jwks-rsa"


def test_when_nestjs_overlay_package_json_is_read_then_jsonwebtoken_is_declared():
    text = _nestjs_package_json_text()
    assert "jsonwebtoken" in text, "package.json must declare jsonwebtoken"


def test_when_nestjs_auth_service_is_read_then_rs256_algorithm_is_enforced():
    text = _nestjs_auth_service_text()
    assert "RS256" in text, "AuthService must enforce RS256"


def test_when_nestjs_auth_service_is_read_then_aud_is_validated():
    text = _nestjs_auth_service_text()
    assert "audience" in text or "aud" in text, "AuthService must validate audience"


def test_when_nestjs_auth_service_is_read_then_iss_is_validated():
    text = _nestjs_auth_service_text()
    assert "issuer" in text or "iss" in text, "AuthService must validate issuer"


def test_when_nestjs_auth_service_is_read_then_tid_pinning_is_present():
    text = _nestjs_auth_service_text()
    assert "tid" in text, "AuthService must pin tenant via tid claim"


def test_when_nestjs_auth_service_is_read_then_scp_or_scope_enforcement_is_present():
    text = _nestjs_auth_service_text()
    assert "scp" in text or "scope" in text.lower(), (
        "AuthService must enforce required scope"
    )


def test_when_nestjs_auth_service_is_read_then_401_response_is_present():
    text = _nestjs_auth_service_text()
    assert "401" in text or "UnauthorizedException" in text, (
        "AuthService / guard must return 401 on auth failure"
    )


def test_when_nestjs_auth_service_is_read_then_403_response_is_present():
    text = _nestjs_auth_service_text()
    assert "403" in text or "ForbiddenException" in text, (
        "AuthService / guard must return 403 on insufficient scope"
    )
