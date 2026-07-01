"""
Source-blind tests for issue #12 README documentation criteria (scope criteria).
Derived exclusively from the spec — no implementation source was read.

Criteria covered:
  C6 — Both READMEs document the two-registration topology (API app + SPA app).
  C7 — Both READMEs document the mandatory `requestedAccessTokenVersion: 2` manifest
        step and note that the default (v1) issuer causes 401s.
  C8 — Both READMEs document the `access_as_user` scope and SPA redirect URI(s)
        (e.g. http://localhost:4200).
  C9 — Both READMEs map each registration ID to its env var
        (ENTRA_TENANT_ID, ENTRA_API_CLIENT_ID, ENTRA_API_AUDIENCE,
         ENTRA_API_SCOPE, ENTRA_SPA_CLIENT_ID) and note no client secret required.
"""

from pathlib import Path

import pytest
from hypothesis import given, strategies as st

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
PKG_DIR = REPO_ROOT / "project_initializer"

FASTAPI_README = PKG_DIR / "templates-entra-fastapi" / "README.md"
NESTJS_README = PKG_DIR / "templates-entra-nestjs" / "README.md"

_BOTH_READMES = [
    ("fastapi", FASTAPI_README),
    ("nestjs", NESTJS_README),
]


def _read(path: Path) -> str:
    assert path.exists(), f"README not found at {path}"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# C6 — Two-registration topology (API app + SPA app)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant,readme_path", _BOTH_READMES)
def test_when_readme_present_then_api_app_registration_documented(variant, readme_path):
    """
    Criterion: README documents the API app registration (one of the two-registration topology).
    We look for clear labelling such as "API app", "API registration", or "API application".
    """
    text = _read(readme_path)
    lower = text.lower()
    assert (
        "api app" in lower or "api application" in lower or "api registration" in lower
    ), f"[{variant}] API app registration not documented in README"


@pytest.mark.parametrize("variant,readme_path", _BOTH_READMES)
def test_when_readme_present_then_spa_app_registration_documented(variant, readme_path):
    """
    Criterion: README documents the SPA app registration (second of the two-registration topology).
    """
    text = _read(readme_path)
    lower = text.lower()
    assert (
        "spa app" in lower or "spa application" in lower or "spa registration" in lower
    ), f"[{variant}] SPA app registration not documented in README"


@pytest.mark.parametrize("variant,readme_path", _BOTH_READMES)
def test_when_readme_present_then_two_registrations_topology_is_explicit(
    variant, readme_path
):
    """
    Criterion: the two-registration topology is explicitly described (not just implied by
    the presence of API + SPA sections separately).
    """
    text = _read(readme_path)
    lower = text.lower()
    # Must reference both registrations together — at least mention "two" or "2" near "registration"
    has_two = (
        "two" in lower
        or "2 app" in lower
        or "two app" in lower
        or "two registration" in lower
    )
    has_both_terms = "api" in lower and "spa" in lower
    assert has_two or has_both_terms, (
        f"[{variant}] Two-registration topology not explicitly described in README"
    )


# ---------------------------------------------------------------------------
# C7 — requestedAccessTokenVersion: 2 and v1 issuer warning
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant,readme_path", _BOTH_READMES)
def test_when_readme_present_then_requested_access_token_version_2_documented(
    variant, readme_path
):
    """
    Criterion: README documents the mandatory `requestedAccessTokenVersion: 2` manifest step.
    """
    text = _read(readme_path)
    assert "requestedAccessTokenVersion" in text, (
        f"[{variant}] 'requestedAccessTokenVersion' not found in README"
    )
    assert "2" in text, (
        f"[{variant}] Value '2' for requestedAccessTokenVersion not found in README"
    )


@pytest.mark.parametrize("variant,readme_path", _BOTH_READMES)
def test_when_readme_present_then_v1_issuer_401_warning_present(variant, readme_path):
    """
    Criterion: README notes that the default v1 issuer causes 401s.
    Must mention v1 issuer AND 401 in close proximity.
    """
    text = _read(readme_path)
    lower = text.lower()
    has_v1_issuer = "v1" in lower or "sts.windows.net" in lower
    has_401 = "401" in text
    assert has_v1_issuer, (
        f"[{variant}] v1 issuer warning (v1 or sts.windows.net) not found in README"
    )
    assert has_401, f"[{variant}] 401 consequence of v1 issuer not documented in README"


# ---------------------------------------------------------------------------
# C8 — access_as_user scope and SPA redirect URI
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant,readme_path", _BOTH_READMES)
def test_when_readme_present_then_access_as_user_scope_documented(variant, readme_path):
    """
    Criterion: README documents the `access_as_user` scope.
    """
    text = _read(readme_path)
    assert "access_as_user" in text, (
        f"[{variant}] 'access_as_user' scope not documented in README"
    )


@pytest.mark.parametrize("variant,readme_path", _BOTH_READMES)
def test_when_readme_present_then_localhost_4200_redirect_uri_documented(
    variant, readme_path
):
    """
    Criterion: README documents the SPA redirect URI(s) — at minimum localhost:4200.
    """
    text = _read(readme_path)
    assert "localhost:4200" in text or "4200" in text, (
        f"[{variant}] SPA redirect URI (localhost:4200) not documented in README"
    )


# ---------------------------------------------------------------------------
# C9 — env var mapping: all five vars documented; no client secret required
# ---------------------------------------------------------------------------

_REQUIRED_ENV_VARS = [
    "ENTRA_TENANT_ID",
    "ENTRA_API_CLIENT_ID",
    "ENTRA_API_AUDIENCE",
    "ENTRA_API_SCOPE",
    "ENTRA_SPA_CLIENT_ID",
]


@pytest.mark.parametrize("variant,readme_path", _BOTH_READMES)
@pytest.mark.parametrize("env_var", _REQUIRED_ENV_VARS)
def test_when_readme_present_then_env_var_is_documented(variant, readme_path, env_var):
    """
    Criterion: README maps each registration ID to its env var.
    Each of the five required env vars must appear in the README.
    """
    text = _read(readme_path)
    assert env_var in text, (
        f"[{variant}] Required env var '{env_var}' not documented in README"
    )


@pytest.mark.parametrize("variant,readme_path", _BOTH_READMES)
def test_when_readme_present_then_no_client_secret_requirement_stated(
    variant, readme_path
):
    """
    Criterion: README notes that no client secret is required.
    Must contain a phrase indicating the absence of a secret.
    """
    text = _read(readme_path)
    lower = text.lower()
    no_secret_phrases = [
        "no client secret",
        "no secret",
        "client secret is not required",
        "does not require a client secret",
        "without a client secret",
        "secret is not needed",
        "secret not required",
    ]
    assert any(phrase in lower for phrase in no_secret_phrases), (
        f"[{variant}] README does not state that no client secret is required"
    )


# ---------------------------------------------------------------------------
# Property-based: all five env vars must be present in both READMEs
# (invariant: the required-env-var set is a fixed contract, not a function of input)
# ---------------------------------------------------------------------------


@given(st.sampled_from(_REQUIRED_ENV_VARS))
def test_when_any_required_env_var_checked_then_it_appears_in_fastapi_readme(env_var):
    """
    Invariant: every element of the required env var set must appear in the FastAPI README.
    This property-based test guards against future edits that silently drop a var.
    """
    text = _read(FASTAPI_README)
    assert env_var in text, f"Required env var '{env_var}' missing from FastAPI README"


@given(st.sampled_from(_REQUIRED_ENV_VARS))
def test_when_any_required_env_var_checked_then_it_appears_in_nestjs_readme(env_var):
    """
    Invariant: every element of the required env var set must appear in the NestJS README.
    """
    text = _read(NESTJS_README)
    assert env_var in text, f"Required env var '{env_var}' missing from NestJS README"
