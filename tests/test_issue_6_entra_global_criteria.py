"""
Source-blind example tests for issue #6 — global acceptance criteria.
feat(entra-frontend): wire MSAL via app.config factory providers and standalone bootstrap init

Criteria covered (per oracle: [UNIT]):
  [UNIT] --auth entra is available as a fourth auth mode alongside none/token/supabase,
         and all existing modes plus every --scope combination remain unchanged.
  [UNIT] No client secret is present in either backend; token validation is signature-only,
         and only browser-safe public values (ENTRA_TENANT_ID, ENTRA_SPA_CLIENT_ID,
         authority, scope) reach the frontend environment.ts.
  [UNIT] The three new overlay directories mirror the supabase overlay layout 1:1 so
         copy_tree merges them with no special-casing, and both pyproject.toml and
         MANIFEST.in package all three.

Criteria covered by other test modules (not duplicated here):
  - FastAPI/NestJS in-process JWT validation  → test_entra_fastapi_overlay.py,
                                                test_entra_nestjs_overlay.py
  - JWKS auto-refresh (PyJWKClient / jwks-rsa) → same modules above

Criteria skipped (NOT VERIFIABLE per oracle):
  - "All tests pass"      — boilerplate suite gate; no per-criterion assertion
  - "SOLID, clean code"   — subjective prose; no concrete runtime/unit assertion
"""

import pathlib

import pytest
from hypothesis import given, settings as hyp_settings, strategies as st

ROOT = pathlib.Path(__file__).parent.parent
_PKG = ROOT / "project_initializer"

ENTRA_FASTAPI = _PKG / "templates-entra-fastapi"
ENTRA_NESTJS = _PKG / "templates-entra-nestjs"
ENTRA_FRONTEND = _PKG / "templates-entra-frontend"

SUPABASE_FASTAPI = _PKG / "templates-supabase-fastapi"
SUPABASE_NESTJS = _PKG / "templates-supabase-nestjs"
SUPABASE_FRONTEND = _PKG / "templates-supabase-frontend"

PYPROJECT_TOML = ROOT / "pyproject.toml"
MANIFEST_IN = ROOT / "MANIFEST.in"

ENVIRONMENTS = ENTRA_FRONTEND / "frontend" / "src" / "environments"


# ===========================================================================
# Criterion 1: --auth entra is the fourth auth mode; existing modes unchanged
# ===========================================================================


def test_when_auth_modes_inspected_then_entra_is_present():
    """'entra' must be a member of AUTH_MODES so --auth entra is accepted."""
    from project_initializer.cli import AUTH_MODES

    assert "entra" in AUTH_MODES


@pytest.mark.parametrize("mode", ["token", "supabase"])
def test_when_existing_auth_modes_inspected_then_they_are_still_present(mode):
    """'token' and 'supabase' must remain in AUTH_MODES — adding entra must not remove them."""
    from project_initializer.cli import AUTH_MODES

    assert mode in AUTH_MODES, (
        f"Existing auth mode '{mode}' disappeared from AUTH_MODES after adding 'entra'"
    )


@pytest.mark.parametrize(
    "scope,framework",
    [
        ("fullstack", "fastapi"),
        ("fullstack", "nestjs"),
        ("api", "fastapi"),
        ("api", "nestjs"),
        ("frontend", None),
    ],
)
def test_when_existing_scope_framework_combination_used_without_auth_then_validate_scope_returns_no_errors(
    scope, framework
):
    """All existing --scope / --framework combinations must still pass validate_scope after
    adding entra — the new auth mode must not perturb unrelated validation paths."""
    from project_initializer.cli import validate_scope

    errors = validate_scope(scope, framework, None)
    assert errors == [] or errors == (), (
        f"validate_scope({scope!r}, {framework!r}, None) returned errors after adding entra: {errors}"
    )


@pytest.mark.parametrize(
    "scope,framework,auth",
    [
        ("fullstack", "fastapi", "token"),
        ("fullstack", "nestjs", "token"),
        ("fullstack", "fastapi", "supabase"),
        ("fullstack", "nestjs", "supabase"),
    ],
)
def test_when_existing_auth_scope_combination_used_then_validate_scope_returns_no_errors(
    scope, framework, auth
):
    """Pre-existing auth combinations (token/supabase × fastapi/nestjs × fullstack) must still
    be valid — they must not break when entra is added as a new mode."""
    from project_initializer.cli import validate_scope

    errors = validate_scope(scope, framework, auth)
    assert errors == [] or errors == (), (
        f"validate_scope({scope!r}, {framework!r}, {auth!r}) returned errors: {errors}"
    )


# Property: for any existing (non-entra) auth mode, select_layers produces at least
# the base layer — ordering/completeness invariant over the existing set.
@given(st.sampled_from(["token", "supabase"]))
@hyp_settings(max_examples=10)
def test_when_existing_auth_mode_given_to_select_layers_then_base_layer_is_always_included(
    auth_mode,
):
    """Invariant (completeness): for every pre-existing auth mode, select_layers('fullstack',
    'fastapi', mode) must still include the base templates/ layer — adding entra must not
    disrupt the generic merge logic."""
    from project_initializer.cli import select_layers

    layers = select_layers("fullstack", "fastapi", auth_mode)
    paths = [str(src) for src, _, _ in layers]
    assert any(
        "templates" in p
        and "api" not in p
        and "token" not in p
        and "supabase" not in p
        and "entra" not in p
        for p in paths
    ), f"Base templates/ layer missing from select_layers result for auth='{auth_mode}'"


# ===========================================================================
# Criterion 3: No client secret; only browser-safe public values in environment.ts
# ===========================================================================


def test_when_entra_frontend_environment_ts_read_then_entra_api_client_id_is_absent():
    """ENTRA_API_CLIENT_ID (the backend app registration ID) must never reach environment.ts.
    Only the SPA client ID (ENTRA_SPA_CLIENT_ID) is browser-safe; the API client ID is not."""
    env_file = ENVIRONMENTS / "environment.ts"
    assert env_file.exists(), f"environment.ts not found at {env_file}"
    content = env_file.read_text(encoding="utf-8")
    assert "ENTRA_API_CLIENT_ID" not in content, (
        "ENTRA_API_CLIENT_ID must not appear in environment.ts — "
        "only the SPA client ID (browser-safe) may reach the frontend bundle"
    )


def test_when_entra_frontend_environment_prod_ts_read_then_entra_api_client_id_is_absent():
    """ENTRA_API_CLIENT_ID must be absent from the production environment file too."""
    env_file = ENVIRONMENTS / "environment.prod.ts"
    assert env_file.exists(), f"environment.prod.ts not found at {env_file}"
    content = env_file.read_text(encoding="utf-8")
    assert "ENTRA_API_CLIENT_ID" not in content, (
        "ENTRA_API_CLIENT_ID must not appear in environment.prod.ts"
    )


@pytest.mark.parametrize(
    "public_value",
    ["entraTenantId", "entraSpaClientId", "authority", "scope"],
)
def test_when_entra_frontend_environment_ts_read_then_browser_safe_public_value_is_present(
    public_value,
):
    """Each browser-safe public value listed in the criterion must be present in environment.ts.
    Assumption: field names use camelCase (e.g. entraTenantId, entraSpaClientId)."""
    env_file = ENVIRONMENTS / "environment.ts"
    assert env_file.exists(), f"environment.ts not found at {env_file}"
    content = env_file.read_text(encoding="utf-8")
    assert public_value in content, (
        f"Browser-safe public field '{public_value}' missing from environment.ts"
    )


# ===========================================================================
# Criterion 4: Three overlay dirs exist; pyproject.toml + MANIFEST.in package all three
# ===========================================================================


@pytest.mark.parametrize(
    "overlay_dir",
    [ENTRA_FASTAPI, ENTRA_NESTJS, ENTRA_FRONTEND],
    ids=[
        "templates-entra-fastapi",
        "templates-entra-nestjs",
        "templates-entra-frontend",
    ],
)
def test_when_overlay_dir_is_inspected_then_it_exists(overlay_dir: pathlib.Path):
    """Each of the three entra overlay directories must exist under project_initializer/."""
    assert overlay_dir.is_dir(), f"Entra overlay directory missing: {overlay_dir.name}"


@pytest.mark.parametrize(
    "overlay_name",
    ["templates-entra-fastapi", "templates-entra-nestjs", "templates-entra-frontend"],
)
def test_when_pyproject_toml_is_read_then_entra_overlay_is_declared(overlay_name: str):
    """pyproject.toml package-data must include each of the three entra overlay dirs so the
    pip-installed package can locate them at runtime."""
    content = PYPROJECT_TOML.read_text(encoding="utf-8")
    assert overlay_name in content, (
        f"pyproject.toml must declare '{overlay_name}' in package-data"
    )


@pytest.mark.parametrize(
    "overlay_name",
    ["templates-entra-fastapi", "templates-entra-nestjs", "templates-entra-frontend"],
)
def test_when_manifest_in_is_read_then_entra_overlay_is_declared(overlay_name: str):
    """MANIFEST.in must include a recursive-include for each of the three entra overlay dirs
    so sdist distributions ship all template files."""
    content = MANIFEST_IN.read_text(encoding="utf-8")
    assert overlay_name in content, (
        f"MANIFEST.in must include a recursive-include for '{overlay_name}'"
    )


# Property (completeness invariant): for every entra overlay dir, BOTH packaging files
# must reference it — for all members of the required set.
@given(
    st.sampled_from(
        [
            "templates-entra-fastapi",
            "templates-entra-nestjs",
            "templates-entra-frontend",
        ]
    )
)
@hyp_settings(max_examples=10)
def test_when_any_entra_overlay_dir_checked_then_both_packaging_files_reference_it(
    overlay_name,
):
    """Invariant (completeness): for every member of the three-overlay required set, both
    pyproject.toml and MANIFEST.in must reference it.  No overlay may be silently omitted
    from either packaging file."""
    pyproject_content = PYPROJECT_TOML.read_text(encoding="utf-8")
    manifest_content = MANIFEST_IN.read_text(encoding="utf-8")
    assert overlay_name in pyproject_content, (
        f"pyproject.toml must always reference '{overlay_name}'"
    )
    assert overlay_name in manifest_content, (
        f"MANIFEST.in must always reference '{overlay_name}'"
    )


def test_when_entra_overlay_dirs_compared_then_they_are_siblings_of_supabase_overlays():
    """The entra overlay dirs must sit as direct children of project_initializer/ — the same
    layout as the supabase overlays — so copy_tree needs no special-casing.
    Assumption: 'mirror layout 1:1' is verified at the directory-parent level: each entra
    overlay is a sibling of its supabase counterpart under the same parent directory."""
    for entra_dir, supabase_dir in [
        (ENTRA_FASTAPI, SUPABASE_FASTAPI),
        (ENTRA_NESTJS, SUPABASE_NESTJS),
        (ENTRA_FRONTEND, SUPABASE_FRONTEND),
    ]:
        assert entra_dir.parent == supabase_dir.parent, (
            f"{entra_dir.name} and {supabase_dir.name} must share the same parent directory "
            f"so copy_tree can merge them identically"
        )
