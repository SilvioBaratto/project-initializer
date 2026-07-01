"""
Source-blind tests for issue #5:
feat(entra-frontend): scaffold overlay foundation — MSAL deps and public-only environment

Criteria verified (derived from acceptance criteria, not from implementation):
- [UNIT] package.json lists @azure/msal-angular and @azure/msal-browser at v4, removes
  @supabase/supabase-js, and preserves base scripts + prettier config
- [UNIT] environment.model.ts declares AppEnvironment with apiUrl, entraTenantId,
  entraSpaClientId, authority, scope — and no secret-bearing field
- [UNIT] environment.ts (dev) sets apiUrl='http://127.0.0.1:8000/api/v1/', no secrets
- [UNIT] environment.prod.ts sets apiUrl='/api/v1/', no secrets
- [UNIT] authority placeholder follows https://login.microsoftonline.com/<tenant-id> format
- [UNIT] scope placeholder uses the access_as_user API scope URI format
- [UNIT] pyproject.toml and MANIFEST.in both reference templates-entra-frontend/
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
ENTRA_FRONTEND = ROOT / "project_initializer" / "templates-entra-frontend"
FRONTEND_DIR = ENTRA_FRONTEND / "frontend"
ENVIRONMENTS = FRONTEND_DIR / "src" / "environments"

# ---------------------------------------------------------------------------
# package.json — MSAL dependencies, no supabase, base scripts preserved
# ---------------------------------------------------------------------------


def test_when_entra_frontend_package_json_is_read_then_msal_angular_v4_is_listed():
    """@azure/msal-angular must be declared at major version 4 to align with Angular 21."""
    pkg = json.loads((FRONTEND_DIR / "package.json").read_text(encoding="utf-8"))
    deps = pkg.get("dependencies", {})
    assert "@azure/msal-angular" in deps, (
        "@azure/msal-angular missing from dependencies"
    )
    ver = deps["@azure/msal-angular"]
    assert re.match(r"[\^~]?4\.", ver), (
        f"@azure/msal-angular version '{ver}' must be major 4 to align with Angular 21"
    )


def test_when_entra_frontend_package_json_is_read_then_msal_browser_v4_is_listed():
    """@azure/msal-browser must be declared at major version 4 to pair with msal-angular v4."""
    pkg = json.loads((FRONTEND_DIR / "package.json").read_text(encoding="utf-8"))
    deps = pkg.get("dependencies", {})
    assert "@azure/msal-browser" in deps, (
        "@azure/msal-browser missing from dependencies"
    )
    ver = deps["@azure/msal-browser"]
    assert re.match(r"[\^~]?4\.", ver), (
        f"@azure/msal-browser version '{ver}' must be major 4"
    )


def test_when_entra_frontend_package_json_is_read_then_supabase_js_is_absent():
    """@supabase/supabase-js must be removed; the entra overlay does not use Supabase."""
    pkg = json.loads((FRONTEND_DIR / "package.json").read_text(encoding="utf-8"))
    all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "@supabase/supabase-js" not in all_deps


def test_when_entra_frontend_package_json_is_read_then_base_scripts_are_preserved():
    """Base scripts (ng, start, build, watch, test) must be mirrored from the base template."""
    pkg = json.loads((FRONTEND_DIR / "package.json").read_text(encoding="utf-8"))
    scripts = pkg.get("scripts", {})
    for script in ("ng", "start", "build", "watch", "test"):
        assert script in scripts, (
            f"Base script '{script}' missing from package.json scripts"
        )


def test_when_entra_frontend_package_json_is_read_then_prettier_config_is_present():
    """Prettier config must be preserved (criterion: mirrors base scripts/prettier/devDeps)."""
    pkg = json.loads((FRONTEND_DIR / "package.json").read_text(encoding="utf-8"))
    assert "prettier" in pkg, "prettier config missing from package.json"


# ---------------------------------------------------------------------------
# environment.model.ts — AppEnvironment interface: five public fields, no secrets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field", ["apiUrl", "entraTenantId", "entraSpaClientId", "authority", "scope"]
)
def test_when_environment_model_is_read_then_required_field_is_declared(field):
    """AppEnvironment must declare each of the five public fields from the criterion."""
    content = (ENVIRONMENTS / "environment.model.ts").read_text(encoding="utf-8")
    assert field in content, (
        f"Field '{field}' missing from AppEnvironment in environment.model.ts"
    )


@pytest.mark.parametrize(
    "secret_field", ["clientSecret", "ENTRA_API_CLIENT_ID", "apiClientId"]
)
def test_when_environment_model_is_read_then_secret_bearing_field_is_absent(
    secret_field,
):
    """AppEnvironment must not expose any secret-bearing field; the SPA uses no client secret."""
    content = (ENVIRONMENTS / "environment.model.ts").read_text(encoding="utf-8")
    assert secret_field not in content, (
        f"Secret-bearing field '{secret_field}' must not appear in AppEnvironment"
    )


# ---------------------------------------------------------------------------
# environment.ts (dev) — correct apiUrl, authority format, scope format, no secrets
# ---------------------------------------------------------------------------


def test_when_dev_environment_is_read_then_api_url_is_local_dev_address():
    """Dev environment.ts must set apiUrl to the local development API address."""
    content = (ENVIRONMENTS / "environment.ts").read_text(encoding="utf-8")
    assert "http://127.0.0.1:8000/api/v1/" in content


def test_when_dev_environment_is_read_then_authority_follows_microsoftonline_format():
    """authority must use https://login.microsoftonline.com/<tenant-id> base URL."""
    content = (ENVIRONMENTS / "environment.ts").read_text(encoding="utf-8")
    assert "https://login.microsoftonline.com/" in content


def test_when_dev_environment_is_read_then_scope_contains_access_as_user():
    """scope must use the access_as_user API scope URI (api://<api-client-id>/access_as_user)."""
    content = (ENVIRONMENTS / "environment.ts").read_text(encoding="utf-8")
    assert "access_as_user" in content


@pytest.mark.parametrize("forbidden", ["clientSecret", "ENTRA_API_CLIENT_ID", "secret"])
def test_when_dev_environment_is_read_then_no_secret_keyword_is_present(forbidden):
    """grep confirms no 'secret'/'clientSecret'/'ENTRA_API_CLIENT_ID' in environment.ts."""
    content = (ENVIRONMENTS / "environment.ts").read_text(encoding="utf-8")
    assert forbidden not in content, (
        f"Forbidden keyword '{forbidden}' found in environment.ts — must not reach the browser bundle"
    )


# ---------------------------------------------------------------------------
# environment.prod.ts — correct apiUrl, authority format, scope format, no secrets
# ---------------------------------------------------------------------------


def test_when_prod_environment_is_read_then_api_url_is_relative_proxy_path():
    """Prod environment.prod.ts must use the relative /api/v1/ path (served via nginx proxy)."""
    content = (ENVIRONMENTS / "environment.prod.ts").read_text(encoding="utf-8")
    # The criterion specifies apiUrl: '/api/v1/' — check for the relative path string
    assert "/api/v1/" in content


def test_when_prod_environment_is_read_then_authority_follows_microsoftonline_format():
    content = (ENVIRONMENTS / "environment.prod.ts").read_text(encoding="utf-8")
    assert "https://login.microsoftonline.com/" in content


def test_when_prod_environment_is_read_then_scope_contains_access_as_user():
    content = (ENVIRONMENTS / "environment.prod.ts").read_text(encoding="utf-8")
    assert "access_as_user" in content


@pytest.mark.parametrize("forbidden", ["clientSecret", "ENTRA_API_CLIENT_ID", "secret"])
def test_when_prod_environment_is_read_then_no_secret_keyword_is_present(forbidden):
    """grep confirms no 'secret'/'clientSecret'/'ENTRA_API_CLIENT_ID' in environment.prod.ts."""
    content = (ENVIRONMENTS / "environment.prod.ts").read_text(encoding="utf-8")
    assert forbidden not in content, (
        f"Forbidden keyword '{forbidden}' found in environment.prod.ts"
    )


# ---------------------------------------------------------------------------
# Packaging: pyproject.toml and MANIFEST.in must cover templates-entra-frontend/
# ---------------------------------------------------------------------------


def test_when_pyproject_toml_is_read_then_templates_entra_frontend_is_declared():
    """pyproject.toml package-data must include templates-entra-frontend/ for distribution."""
    content = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "templates-entra-frontend" in content, (
        "templates-entra-frontend/ missing from pyproject.toml package-data"
    )


def test_when_manifest_in_is_read_then_templates_entra_frontend_is_declared():
    """MANIFEST.in must contain a recursive-include for templates-entra-frontend/ (sdist)."""
    content = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "templates-entra-frontend" in content, (
        "templates-entra-frontend/ missing from MANIFEST.in"
    )
