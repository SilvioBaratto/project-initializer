"""
Issue #13 — Criterion: No client secret is present in either backend; token validation is
signature-only, and only browser-safe public values (ENTRA_TENANT_ID, ENTRA_SPA_CLIENT_ID,
authority, scope) reach the frontend environment.ts.
"""

import pathlib
import re

OVERLAY_FASTAPI = pathlib.Path("project_initializer/templates-entra-fastapi")
OVERLAY_NESTJS = pathlib.Path("project_initializer/templates-entra-nestjs")
OVERLAY_FRONTEND = pathlib.Path("project_initializer/templates-entra-frontend")

_SECRET_PATTERN = re.compile(r"client[_-]?secret", re.IGNORECASE)
_ENV_EXAMPLE_FASTAPI = OVERLAY_FASTAPI / "api" / ".env.example"
_ENV_EXAMPLE_NESTJS = OVERLAY_NESTJS / "api" / ".env.example"


def test_when_fastapi_env_example_is_read_then_no_client_secret_key_is_present():
    text = _ENV_EXAMPLE_FASTAPI.read_text(encoding="utf-8")
    assert not _SECRET_PATTERN.search(text), (
        "FastAPI .env.example must not contain any client_secret variable"
    )


def test_when_nestjs_env_example_is_read_then_no_client_secret_key_is_present():
    text = _ENV_EXAMPLE_NESTJS.read_text(encoding="utf-8")
    assert not _SECRET_PATTERN.search(text), (
        "NestJS .env.example must not contain any client_secret variable"
    )


def test_when_fastapi_dependencies_are_read_then_no_client_secret_usage_is_present():
    deps = OVERLAY_FASTAPI / "api" / "app" / "dependencies.py"
    text = deps.read_text(encoding="utf-8")
    assert not _SECRET_PATTERN.search(text), (
        "FastAPI dependencies.py must not use a client_secret"
    )


def test_when_nestjs_auth_service_is_read_then_no_client_secret_usage_is_present():
    matches = list(OVERLAY_NESTJS.rglob("auth.service.ts"))
    assert matches, "auth.service.ts not found in templates-entra-nestjs/"
    text = matches[0].read_text(encoding="utf-8")
    assert not _SECRET_PATTERN.search(text), (
        "NestJS AuthService must not use a client_secret"
    )


def test_when_frontend_environment_ts_is_read_then_tenant_id_is_present():
    """ENTRA_TENANT_ID (or tenantId) must reach environment.ts — it is public."""
    matches = list(OVERLAY_FRONTEND.rglob("environment.ts"))
    assert matches, "environment.ts not found in templates-entra-frontend/"
    text = matches[0].read_text(encoding="utf-8")
    assert "tenantId" in text or "ENTRA_TENANT_ID" in text, (
        "environment.ts must expose tenantId (ENTRA_TENANT_ID)"
    )


def test_when_frontend_environment_ts_is_read_then_spa_client_id_is_present():
    """ENTRA_SPA_CLIENT_ID (clientId) must reach environment.ts — it is public."""
    matches = list(OVERLAY_FRONTEND.rglob("environment.ts"))
    assert matches, "environment.ts not found in templates-entra-frontend/"
    text = matches[0].read_text(encoding="utf-8")
    assert "clientId" in text or "ENTRA_SPA_CLIENT_ID" in text, (
        "environment.ts must expose clientId (ENTRA_SPA_CLIENT_ID)"
    )


def test_when_frontend_environment_ts_is_read_then_no_client_secret_is_present():
    """A client secret must never appear in the frontend bundle."""
    matches = list(OVERLAY_FRONTEND.rglob("environment.ts"))
    assert matches, "environment.ts not found in templates-entra-frontend/"
    text = matches[0].read_text(encoding="utf-8")
    assert not _SECRET_PATTERN.search(text), (
        "environment.ts must never contain a client secret"
    )


# ---------------------------------------------------------------------------
# Property: for every .ts file in the frontend overlay, no client_secret appears.
# Invariant: "only browser-safe public values reach the frontend" must hold for
# ALL files in the overlay, not just environment.ts.
# ---------------------------------------------------------------------------


def _all_frontend_ts_texts():
    return [p.read_text(encoding="utf-8") for p in OVERLAY_FRONTEND.rglob("*.ts")]


def test_when_all_frontend_ts_files_are_scanned_then_none_contain_client_secret():
    """Invariant: client_secret must be absent from every TypeScript file in the frontend overlay."""
    for path in OVERLAY_FRONTEND.rglob("*.ts"):
        text = path.read_text(encoding="utf-8")
        assert not _SECRET_PATTERN.search(text), (
            f"{path} must not contain a client_secret"
        )
