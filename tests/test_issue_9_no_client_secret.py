"""
Source-blind tests for issue #9 — criterion 3:
  No client secret is present in either backend; token validation is
  signature-only, and only browser-safe public values (ENTRA_TENANT_ID,
  ENTRA_SPA_CLIENT_ID, authority, scope) reach the frontend environment.ts.

Tests are authored from the acceptance criteria only; no implementation source was read.
Assumption: 'no client secret' means no variable or key literally named CLIENT_SECRET
(or ENTRA_CLIENT_SECRET / AZURE_CLIENT_SECRET) appears in the backend overlay source
or its .env.example.  A secret-free backend performs signature-only JWT validation via
the public JWKS endpoint.
"""

import re
from pathlib import Path

import pytest

_PKG = Path(__file__).parent.parent / "project_initializer"
_FASTAPI_OVERLAY = _PKG / "templates-entra-fastapi"
_NESTJS_OVERLAY = _PKG / "templates-entra-nestjs"
_FRONTEND_OVERLAY = _PKG / "templates-entra-frontend"

# Patterns that would indicate a client secret in backend source
_SECRET_PATTERNS = [
    re.compile(r"CLIENT_SECRET", re.IGNORECASE),
    re.compile(r"client_secret", re.IGNORECASE),
    re.compile(r"ENTRA_SECRET", re.IGNORECASE),
    re.compile(r"AZURE_SECRET", re.IGNORECASE),
]

# Browser-safe values that MUST appear in environment.ts
_REQUIRED_FRONTEND_VARS = [
    "ENTRA_TENANT_ID",
    "ENTRA_SPA_CLIENT_ID",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _all_source_text(root: Path, *suffixes: str) -> str:
    parts = []
    for suffix in suffixes:
        parts.extend(_read(f) for f in root.rglob(f"*{suffix}"))
    return "\n".join(parts)


def _contains_secret(text: str) -> bool:
    return any(p.search(text) for p in _SECRET_PATTERNS)


# ---------------------------------------------------------------------------
# Criterion 3a — no client secret in FastAPI backend overlay source
# ---------------------------------------------------------------------------


def test_when_fastapi_overlay_present_then_no_client_secret_is_in_source():
    """FastAPI overlay Python source must not contain any CLIENT_SECRET variable."""
    if not _FASTAPI_OVERLAY.is_dir():
        pytest.fail("templates-entra-fastapi/ does not exist yet (Red phase expected)")
    source = _all_source_text(_FASTAPI_OVERLAY, ".py")
    assert not _contains_secret(source), (
        "FastAPI overlay must not declare a client secret; validation is signature-only"
    )


def test_when_fastapi_overlay_env_example_present_then_no_client_secret_is_listed():
    """FastAPI overlay .env.example must not contain a CLIENT_SECRET key."""
    if not _FASTAPI_OVERLAY.is_dir():
        pytest.fail("templates-entra-fastapi/ does not exist yet (Red phase expected)")
    env_files = list(_FASTAPI_OVERLAY.rglob(".env.example"))
    assert env_files, "templates-entra-fastapi/ must contain a .env.example file"
    content = "\n".join(_read(f) for f in env_files)
    assert not _contains_secret(content), (
        ".env.example in FastAPI overlay must not list a client secret"
    )


# ---------------------------------------------------------------------------
# Criterion 3b — no client secret in NestJS backend overlay source
# ---------------------------------------------------------------------------


def test_when_nestjs_overlay_present_then_no_client_secret_is_in_source():
    """NestJS overlay TypeScript source must not contain any CLIENT_SECRET variable."""
    if not _NESTJS_OVERLAY.is_dir():
        pytest.fail("templates-entra-nestjs/ does not exist yet (Red phase expected)")
    source = _all_source_text(_NESTJS_OVERLAY, ".ts")
    assert not _contains_secret(source), (
        "NestJS overlay must not declare a client secret; validation is signature-only"
    )


def test_when_nestjs_overlay_env_example_present_then_no_client_secret_is_listed():
    """NestJS overlay .env.example must not contain a CLIENT_SECRET key."""
    if not _NESTJS_OVERLAY.is_dir():
        pytest.fail("templates-entra-nestjs/ does not exist yet (Red phase expected)")
    env_files = list(_NESTJS_OVERLAY.rglob(".env.example"))
    assert env_files, "templates-entra-nestjs/ must contain a .env.example file"
    content = "\n".join(_read(f) for f in env_files)
    assert not _contains_secret(content), (
        ".env.example in NestJS overlay must not list a client secret"
    )


# ---------------------------------------------------------------------------
# Criterion 3c — frontend environment.ts contains only browser-safe public values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("var_name", _REQUIRED_FRONTEND_VARS)
def test_when_frontend_overlay_present_then_browser_safe_var_is_in_environment_ts(
    var_name,
):
    """Frontend environment.ts must expose each required browser-safe public value."""
    if not _FRONTEND_OVERLAY.is_dir():
        pytest.fail("templates-entra-frontend/ does not exist yet (Red phase expected)")
    env_files = list(_FRONTEND_OVERLAY.rglob("environment.ts"))
    assert env_files, (
        "templates-entra-frontend/ must contain an environment.ts file with public Entra values"
    )
    content = "\n".join(_read(f) for f in env_files)
    assert var_name in content, (
        f"environment.ts must contain the browser-safe value '{var_name}'"
    )


def test_when_frontend_overlay_present_then_no_client_secret_is_in_environment_ts():
    """Frontend environment.ts must never expose a client secret."""
    if not _FRONTEND_OVERLAY.is_dir():
        pytest.fail("templates-entra-frontend/ does not exist yet (Red phase expected)")
    env_files = list(_FRONTEND_OVERLAY.rglob("environment.ts"))
    assert env_files, "templates-entra-frontend/ must contain an environment.ts file"
    content = "\n".join(_read(f) for f in env_files)
    assert not _contains_secret(content), (
        "environment.ts must not expose a client secret; only public SPA values are allowed"
    )
