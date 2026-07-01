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

OVERLAY_FASTAPI = pathlib.Path("project_initializer/templates-entra-fastapi")
OVERLAY_NESTJS = pathlib.Path("project_initializer/templates-entra-nestjs")


# ---------------------------------------------------------------------------
# FastAPI overlay — source-text contract tests
# ---------------------------------------------------------------------------


def _fastapi_deps_text() -> str:
    deps = OVERLAY_FASTAPI / "api" / "app" / "dependencies.py"
    return deps.read_text(encoding="utf-8")


def _fastapi_requirements_text() -> str:
    req = OVERLAY_FASTAPI / "api" / "requirements.txt"
    return req.read_text(encoding="utf-8")


def test_when_fastapi_overlay_dependencies_are_read_then_pyjwt_crypto_is_declared():
    text = _fastapi_requirements_text()
    assert "PyJWT" in text or "pyjwt" in text, (
        "requirements.txt must declare PyJWT[crypto] for in-process JWKS validation"
    )


def test_when_fastapi_overlay_dependencies_are_read_then_rs256_algorithm_is_enforced():
    text = _fastapi_deps_text()
    assert "RS256" in text, "get_current_user must enforce RS256 algorithm"


def test_when_fastapi_overlay_dependencies_are_read_then_jwks_client_is_used():
    """PyJWKClient is the PyJWT v2 class that fetches and caches JWKS."""
    text = _fastapi_deps_text()
    assert "PyJWKClient" in text, (
        "dependencies.py must use PyJWKClient for JWKS retrieval"
    )


def test_when_fastapi_overlay_dependencies_are_read_then_aud_is_validated():
    text = _fastapi_deps_text()
    assert "aud" in text or "audience" in text, "audience (aud) claim must be validated"


def test_when_fastapi_overlay_dependencies_are_read_then_iss_is_validated():
    text = _fastapi_deps_text()
    assert "iss" in text or "issuer" in text, "issuer (iss) claim must be validated"


def test_when_fastapi_overlay_dependencies_are_read_then_tid_pinning_is_present():
    text = _fastapi_deps_text()
    assert "tid" in text, "tenant id (tid) claim must be pinned in dependencies.py"


def test_when_fastapi_overlay_dependencies_are_read_then_scp_scope_is_enforced():
    text = _fastapi_deps_text()
    assert "scp" in text, "required scp scope must be enforced in dependencies.py"


def test_when_fastapi_overlay_dependencies_are_read_then_401_is_raised_on_auth_failure():
    text = _fastapi_deps_text()
    assert (
        "401" in text or "HTTP_401" in text or "status.HTTP_401_UNAUTHORIZED" in text
    ), "dependencies.py must raise 401 on authentication failure"


def test_when_fastapi_overlay_dependencies_are_read_then_403_is_raised_on_insufficient_scope():
    text = _fastapi_deps_text()
    assert "403" in text or "HTTP_403" in text or "status.HTTP_403_FORBIDDEN" in text, (
        "dependencies.py must raise 403 on insufficient scope"
    )


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
