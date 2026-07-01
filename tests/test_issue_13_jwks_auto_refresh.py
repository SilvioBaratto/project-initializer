"""
Issue #13 — Criterion: JWKS signing-key clients auto-refresh on key rotation (PyJWKClient;
jwks-rsa with cache: true, rateLimit: true) with no hard-coded refresh schedule.

Tests read template source text only — they do not import or run generated app code.
"""

import pathlib
import re

OVERLAY_FASTAPI = pathlib.Path("project_initializer/templates-entra-fastapi")
OVERLAY_NESTJS = pathlib.Path("project_initializer/templates-entra-nestjs")


# ---------------------------------------------------------------------------
# FastAPI: PyJWKClient
# ---------------------------------------------------------------------------


def _fastapi_deps_text() -> str:
    deps = OVERLAY_FASTAPI / "api" / "app" / "dependencies.py"
    return deps.read_text(encoding="utf-8")


def test_when_fastapi_dependencies_are_read_then_pyjwkclient_is_used_for_key_fetching():
    """PyJWKClient (not a manual urllib call) handles JWKS fetch + cache + rotation."""
    text = _fastapi_deps_text()
    assert "PyJWKClient" in text, (
        "dependencies.py must use PyJWKClient for automatic JWKS caching and key-rotation"
    )


def test_when_fastapi_dependencies_are_read_then_no_hard_coded_refresh_interval_is_present():
    """No explicit sleep/interval/schedule — PyJWKClient handles rotation internally."""
    text = _fastapi_deps_text()
    hard_coded = re.search(r"sleep\s*\(|refresh_interval\s*=|schedule\.", text)
    assert not hard_coded, (
        "dependencies.py must not hard-code a refresh schedule; PyJWKClient auto-refreshes"
    )


# ---------------------------------------------------------------------------
# NestJS: jwks-rsa with cache + rateLimit
# ---------------------------------------------------------------------------


def _nestjs_auth_service_text() -> str:
    matches = list(OVERLAY_NESTJS.rglob("auth.service.ts"))
    assert matches, "auth.service.ts not found in templates-entra-nestjs/"
    return matches[0].read_text(encoding="utf-8")


def test_when_nestjs_auth_service_is_read_then_jwks_rsa_client_is_used():
    text = _nestjs_auth_service_text()
    assert "jwksRsa" in text or "jwks-rsa" in text or "jwksClient" in text.lower(), (
        "auth.service.ts must use the jwks-rsa client for key fetching"
    )


def test_when_nestjs_auth_service_is_read_then_cache_is_enabled():
    """jwks-rsa must be initialised with cache: true."""
    text = _nestjs_auth_service_text()
    assert "cache" in text and "true" in text, (
        "auth.service.ts must enable caching on the jwks-rsa client (cache: true)"
    )


def test_when_nestjs_auth_service_is_read_then_rate_limit_is_enabled():
    """jwks-rsa must be initialised with rateLimit: true."""
    text = _nestjs_auth_service_text()
    assert "rateLimit" in text, (
        "auth.service.ts must enable rate-limiting on the jwks-rsa client (rateLimit: true)"
    )


def test_when_nestjs_auth_service_is_read_then_no_hard_coded_refresh_schedule_is_present():
    text = _nestjs_auth_service_text()
    hard_coded = re.search(
        r"setTimeout\s*\(|setInterval\s*\(|refreshInterval\s*=", text
    )
    assert not hard_coded, (
        "auth.service.ts must not hard-code a refresh schedule; jwks-rsa handles rotation"
    )
