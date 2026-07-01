"""
Source-blind tests for issue #9 — criteria 2 and 5:

  Criterion 2: Both FastAPI and NestJS backends validate Entra v2 JWT bearer tokens
    in-process, enforcing RS256 + cached JWKS + aud/iss/exp-nbf/tid + scp;
    returning 401 on auth failure and 403 on insufficient scope.

  Criterion 5: JWKS signing-key clients auto-refresh on key rotation (PyJWKClient;
    jwks-rsa with cache: true, rateLimit: true) with no hard-coded refresh schedule.

Tests are authored from the acceptance criteria only; no implementation source was read.
Assumption: 'in-process' means the validation code lives inside the overlay source files,
not in a separate sidecar container — we verify this by checking for the relevant library
calls in the overlay source files.
"""

import re
from pathlib import Path

import pytest

_PKG = Path(__file__).parent.parent / "project_initializer"
_FASTAPI_OVERLAY = _PKG / "templates-entra-fastapi"
_NESTJS_OVERLAY = _PKG / "templates-entra-nestjs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _find_python_files(root: Path):
    return list(root.rglob("*.py"))


def _find_ts_files(root: Path):
    return list(root.rglob("*.ts"))


def _combined_python_source(root: Path) -> str:
    return "\n".join(_read(f) for f in _find_python_files(root))


def _combined_ts_source(root: Path) -> str:
    return "\n".join(_read(f) for f in _find_ts_files(root))


# ---------------------------------------------------------------------------
# Criterion 2a — FastAPI: RS256 algorithm is specified
# ---------------------------------------------------------------------------


def test_when_fastapi_overlay_present_then_rs256_algorithm_is_declared():
    """FastAPI overlay must specify RS256 as the accepted signing algorithm."""
    if not _FASTAPI_OVERLAY.is_dir():
        pytest.fail("templates-entra-fastapi/ does not exist yet (Red phase expected)")
    source = _combined_python_source(_FASTAPI_OVERLAY)
    assert "RS256" in source, (
        "FastAPI overlay must declare RS256 algorithm for JWT validation"
    )


# ---------------------------------------------------------------------------
# Criterion 2b — FastAPI: aud, iss, tid, scp checks are present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("claim", ["aud", "iss", "tid", "scp"])
def test_when_fastapi_overlay_present_then_claim_is_validated(claim):
    """FastAPI overlay must validate each required JWT claim."""
    if not _FASTAPI_OVERLAY.is_dir():
        pytest.fail("templates-entra-fastapi/ does not exist yet (Red phase expected)")
    source = _combined_python_source(_FASTAPI_OVERLAY)
    assert claim in source, (
        f"FastAPI overlay must reference JWT claim '{claim}' for Entra validation"
    )


# ---------------------------------------------------------------------------
# Criterion 2c — FastAPI: 401 on auth failure, 403 on insufficient scope
# ---------------------------------------------------------------------------


def test_when_fastapi_overlay_present_then_401_status_is_returned_on_auth_failure():
    """FastAPI overlay must return HTTP 401 when JWT validation fails."""
    if not _FASTAPI_OVERLAY.is_dir():
        pytest.fail("templates-entra-fastapi/ does not exist yet (Red phase expected)")
    source = _combined_python_source(_FASTAPI_OVERLAY)
    assert "401" in source, (
        "FastAPI overlay must emit HTTP 401 on authentication failure"
    )


def test_when_fastapi_overlay_present_then_403_status_is_returned_on_insufficient_scope():
    """FastAPI overlay must return HTTP 403 when the required scope is missing."""
    if not _FASTAPI_OVERLAY.is_dir():
        pytest.fail("templates-entra-fastapi/ does not exist yet (Red phase expected)")
    source = _combined_python_source(_FASTAPI_OVERLAY)
    assert "403" in source, "FastAPI overlay must emit HTTP 403 on insufficient scope"


# ---------------------------------------------------------------------------
# Criterion 2d — NestJS: RS256 algorithm is specified
# ---------------------------------------------------------------------------


def test_when_nestjs_overlay_present_then_rs256_algorithm_is_declared():
    """NestJS overlay must specify RS256 as the accepted signing algorithm."""
    if not _NESTJS_OVERLAY.is_dir():
        pytest.fail("templates-entra-nestjs/ does not exist yet (Red phase expected)")
    source = _combined_ts_source(_NESTJS_OVERLAY)
    assert "RS256" in source, (
        "NestJS overlay must declare RS256 algorithm for JWT validation"
    )


# ---------------------------------------------------------------------------
# Criterion 2e — NestJS: aud, iss, tid, scp checks are present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("claim", ["aud", "iss", "tid", "scp"])
def test_when_nestjs_overlay_present_then_claim_is_validated(claim):
    """NestJS overlay must validate each required JWT claim."""
    if not _NESTJS_OVERLAY.is_dir():
        pytest.fail("templates-entra-nestjs/ does not exist yet (Red phase expected)")
    source = _combined_ts_source(_NESTJS_OVERLAY)
    assert claim in source, (
        f"NestJS overlay must reference JWT claim '{claim}' for Entra validation"
    )


# ---------------------------------------------------------------------------
# Criterion 2f — NestJS: 401 on auth failure, 403 on insufficient scope
# ---------------------------------------------------------------------------


def test_when_nestjs_overlay_present_then_401_status_is_returned_on_auth_failure():
    """NestJS overlay must return HTTP 401 when JWT validation fails."""
    if not _NESTJS_OVERLAY.is_dir():
        pytest.fail("templates-entra-nestjs/ does not exist yet (Red phase expected)")
    source = _combined_ts_source(_NESTJS_OVERLAY)
    assert "401" in source, (
        "NestJS overlay must emit HTTP 401 on authentication failure"
    )


def test_when_nestjs_overlay_present_then_403_status_is_returned_on_insufficient_scope():
    """NestJS overlay must return HTTP 403 when the required scope is missing."""
    if not _NESTJS_OVERLAY.is_dir():
        pytest.fail("templates-entra-nestjs/ does not exist yet (Red phase expected)")
    source = _combined_ts_source(_NESTJS_OVERLAY)
    assert "403" in source, "NestJS overlay must emit HTTP 403 on insufficient scope"


# ---------------------------------------------------------------------------
# Criterion 5a — FastAPI: PyJWKClient (caching JWKS client) is used
# ---------------------------------------------------------------------------


def test_when_fastapi_overlay_present_then_pyjwkclient_is_used_for_jwks():
    """FastAPI overlay must use PyJWKClient so key rotation is handled without hard-coding."""
    if not _FASTAPI_OVERLAY.is_dir():
        pytest.fail("templates-entra-fastapi/ does not exist yet (Red phase expected)")
    source = _combined_python_source(_FASTAPI_OVERLAY)
    assert "PyJWKClient" in source, (
        "FastAPI overlay must use PyJWKClient for auto-refreshing JWKS on key rotation"
    )


def test_when_fastapi_overlay_present_then_no_hard_coded_refresh_interval_is_present():
    """FastAPI overlay must not hard-code a JWKS refresh schedule (e.g. sleep or timer)."""
    if not _FASTAPI_OVERLAY.is_dir():
        pytest.fail("templates-entra-fastapi/ does not exist yet (Red phase expected)")
    source = _combined_python_source(_FASTAPI_OVERLAY)
    # A hard-coded schedule would look like a numeric 'lifespan' / 'ttl' kwarg on the
    # JWKS client constructor, or explicit time.sleep / threading.Timer calls.
    # We look for the most obvious hard-coded forms.
    assert not re.search(r"lifespan\s*=\s*\d+", source), (
        "FastAPI overlay must not hard-code a JWKS key lifespan/refresh interval"
    )


# ---------------------------------------------------------------------------
# Criterion 5b — NestJS: jwks-rsa with cache:true and rateLimit:true
# ---------------------------------------------------------------------------


def test_when_nestjs_overlay_present_then_jwks_rsa_cache_is_enabled():
    """NestJS overlay must pass cache: true to jwks-rsa so keys are cached on rotation."""
    if not _NESTJS_OVERLAY.is_dir():
        pytest.fail("templates-entra-nestjs/ does not exist yet (Red phase expected)")
    source = _combined_ts_source(_NESTJS_OVERLAY)
    assert "cache" in source and "true" in source, (
        "NestJS overlay must pass cache: true to the jwks-rsa client"
    )
    # More precise: the string 'cache: true' or 'cache:true' must appear
    assert re.search(r"cache\s*:\s*true", source), (
        "NestJS overlay must set cache: true in the jwks-rsa client options"
    )


def test_when_nestjs_overlay_present_then_jwks_rsa_rate_limit_is_enabled():
    """NestJS overlay must pass rateLimit: true to jwks-rsa to prevent JWKS flooding."""
    if not _NESTJS_OVERLAY.is_dir():
        pytest.fail("templates-entra-nestjs/ does not exist yet (Red phase expected)")
    source = _combined_ts_source(_NESTJS_OVERLAY)
    assert re.search(r"rateLimit\s*:\s*true", source), (
        "NestJS overlay must set rateLimit: true in the jwks-rsa client options"
    )


def test_when_nestjs_overlay_present_then_jwks_rsa_package_is_declared():
    """NestJS overlay package.json must declare jwks-rsa as a dependency."""
    if not _NESTJS_OVERLAY.is_dir():
        pytest.fail("templates-entra-nestjs/ does not exist yet (Red phase expected)")
    pkg_files = list(_NESTJS_OVERLAY.rglob("package.json"))
    assert pkg_files, "templates-entra-nestjs/ must contain a package.json"
    content = "\n".join(_read(f) for f in pkg_files)
    assert "jwks-rsa" in content, "package.json must declare jwks-rsa as a dependency"
