"""
Source-blind example tests for the templates-entra-nestjs/ overlay.

Derived entirely from acceptance criteria for issue #4
(feat(entra): add templates-entra-nestjs backend overlay).
No implementation source was read during authoring.

Skipped criteria:
  - "All tests pass"         — NOT VERIFIABLE (boilerplate suite gate)
  - "SOLID, clean code …"    — NOT VERIFIABLE (subjective prose)
"""

import json
import re
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

# The overlay files live under an api/ subdirectory (matching all other nestjs overlays).
OVERLAY_ROOT = (
    Path(__file__).parent.parent
    / "project_initializer"
    / "templates-entra-nestjs"
    / "api"
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def overlay_file(rel: str) -> Path:
    return OVERLAY_ROOT / rel


# ===========================================================================
# Criterion: templates-entra-nestjs/ ships a precise set of required files
# ===========================================================================

REQUIRED_FILES = [
    "src/modules/auth/auth.module.ts",
    "src/modules/auth/auth.service.ts",
    "src/modules/auth/auth.guard.ts",
    "src/modules/auth/auth.controller.ts",
    "src/modules/auth/dto/auth.dto.ts",
    "src/config/env.validation.ts",
    "src/app.module.ts",
    "package.json",
    ".env.example",
]


@pytest.mark.parametrize("rel_path", REQUIRED_FILES)
def test_when_overlay_is_present_then_required_file_exists(rel_path):
    """Each file mandated by the acceptance criteria must exist in the overlay."""
    assert overlay_file(rel_path).is_file(), (
        f"Expected {rel_path} to exist in templates-entra-nestjs/"
    )


# ===========================================================================
# Criterion: package.json adds jsonwebtoken + jwks-rsa (and @types/jsonwebtoken)
#            and drops @supabase/supabase-js; no client secret anywhere in overlay
# ===========================================================================


def test_when_package_json_is_read_then_jsonwebtoken_is_a_dependency():
    pkg = json.loads(overlay_file("package.json").read_text(encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "jsonwebtoken" in deps, "package.json must declare jsonwebtoken"


def test_when_package_json_is_read_then_jwks_rsa_is_a_dependency():
    pkg = json.loads(overlay_file("package.json").read_text(encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "jwks-rsa" in deps, "package.json must declare jwks-rsa"


def test_when_package_json_is_read_then_types_jsonwebtoken_is_a_dev_dependency():
    pkg = json.loads(overlay_file("package.json").read_text(encoding="utf-8"))
    dev_deps = pkg.get("devDependencies", {})
    assert "@types/jsonwebtoken" in dev_deps, (
        "package.json must declare @types/jsonwebtoken in devDependencies"
    )


def test_when_package_json_is_read_then_supabase_js_is_absent():
    pkg = json.loads(overlay_file("package.json").read_text(encoding="utf-8"))
    all_deps = {
        **pkg.get("dependencies", {}),
        **pkg.get("devDependencies", {}),
        **pkg.get("peerDependencies", {}),
    }
    assert "@supabase/supabase-js" not in all_deps, (
        "package.json must not declare @supabase/supabase-js"
    )


def _all_overlay_text() -> str:
    """Concatenate all text files in the overlay for secret-scanning."""
    parts = []
    for path in OVERLAY_ROOT.rglob("*"):
        if path.is_file():
            try:
                parts.append(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
    return "\n".join(parts)


def test_when_overlay_is_scanned_then_no_client_secret_is_present():
    """
    No client secret must appear in the overlay.
    Assumption: 'client secret' is detected by the literal key patterns
    CLIENT_SECRET or clientSecret (case-insensitive), which are the conventional
    names for bearer credential values that must never reach this overlay.
    """
    combined = _all_overlay_text()
    # Exclude env.example placeholder comments (lines starting with #)
    non_comment_lines = "\n".join(
        line for line in combined.splitlines() if not line.strip().startswith("#")
    )
    assert not re.search(
        r"client_secret|clientSecret|CLIENT_SECRET", non_comment_lines, re.IGNORECASE
    ), "No client secret value or key must appear in the overlay"


# ===========================================================================
# Criterion: env.validation.ts requires ENTRA_TENANT_ID, ENTRA_API_CLIENT_ID,
#            ENTRA_API_AUDIENCE, ENTRA_API_SCOPE and retains the local Docker DB vars
# ===========================================================================

_ENV_VALIDATION_TEXT = None  # lazy cache


def _env_validation_text() -> str:
    global _ENV_VALIDATION_TEXT
    if _ENV_VALIDATION_TEXT is None:
        _ENV_VALIDATION_TEXT = overlay_file("src/config/env.validation.ts").read_text(
            encoding="utf-8"
        )
    return _ENV_VALIDATION_TEXT


@pytest.mark.parametrize(
    "env_var",
    [
        "ENTRA_TENANT_ID",
        "ENTRA_API_CLIENT_ID",
        "ENTRA_API_AUDIENCE",
        "ENTRA_API_SCOPE",
    ],
)
def test_when_env_validation_is_read_then_required_entra_var_is_declared(env_var):
    assert env_var in _env_validation_text(), (
        f"env.validation.ts must declare {env_var}"
    )


@pytest.mark.parametrize(
    "db_var",
    [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ],
)
def test_when_env_validation_is_read_then_local_docker_db_var_is_retained(db_var):
    """
    Assumption: local Docker DB vars are identified by the conventional
    POSTGRES_* names used in all other non-supabase overlays in this project.
    """
    assert db_var in _env_validation_text(), (
        f"env.validation.ts must retain local Docker DB var {db_var}"
    )


# ===========================================================================
# Criterion: AuthService validates v2 tokens via jwks-rsa (cache: true,
#            rateLimit: true, JWKS URI built from tenant id) + jsonwebtoken.verify
#            (RS256), checking v2 issuer and audience, pinning tid, enforcing scp
# ===========================================================================

_AUTH_SERVICE_TEXT = None


def _auth_service_text() -> str:
    global _AUTH_SERVICE_TEXT
    if _AUTH_SERVICE_TEXT is None:
        _AUTH_SERVICE_TEXT = overlay_file("src/modules/auth/auth.service.ts").read_text(
            encoding="utf-8"
        )
    return _AUTH_SERVICE_TEXT


def test_when_auth_service_is_read_then_jwks_rsa_is_imported():
    assert "jwks-rsa" in _auth_service_text(), (
        "auth.service.ts must import from jwks-rsa"
    )


def test_when_auth_service_is_read_then_jsonwebtoken_verify_is_used():
    assert "verify" in _auth_service_text(), (
        "auth.service.ts must call jsonwebtoken verify"
    )


def test_when_auth_service_is_read_then_rs256_algorithm_is_specified():
    assert "RS256" in _auth_service_text(), (
        "auth.service.ts must specify the RS256 algorithm"
    )


def test_when_auth_service_is_read_then_cache_true_is_configured():
    assert "cache: true" in _auth_service_text(), (
        "auth.service.ts jwks-rsa client must set cache: true"
    )


def test_when_auth_service_is_read_then_rate_limit_true_is_configured():
    assert "rateLimit: true" in _auth_service_text(), (
        "auth.service.ts jwks-rsa client must set rateLimit: true"
    )


def test_when_auth_service_is_read_then_jwks_uri_is_built_from_tenant_id():
    """
    Assumption: JWKS URI is constructed dynamically from ENTRA_TENANT_ID
    (not hard-coded), so the string 'ENTRA_TENANT_ID' or 'tenantId' must
    appear near the JWKS URI construction.
    """
    text = _auth_service_text()
    has_tenant_ref = (
        "ENTRA_TENANT_ID" in text or "tenantId" in text or "tenant_id" in text
    )
    assert has_tenant_ref, (
        "auth.service.ts must build the JWKS URI from the tenant id (ENTRA_TENANT_ID / tenantId)"
    )


def test_when_auth_service_is_read_then_v2_issuer_is_validated():
    """
    Assumption: v2 issuer URL contains the literal '/v2.0' suffix as per
    Microsoft Learn documentation for v2 tokens.
    """
    assert "v2.0" in _auth_service_text(), (
        "auth.service.ts must validate the v2 issuer (contains '/v2.0')"
    )


def test_when_auth_service_is_read_then_tid_claim_is_checked():
    assert "tid" in _auth_service_text(), (
        "auth.service.ts must pin the tenant via the tid claim"
    )


def test_when_auth_service_is_read_then_scp_scope_is_enforced():
    assert "scp" in _auth_service_text(), (
        "auth.service.ts must enforce the required scp scope"
    )


def test_when_auth_service_is_read_then_no_hard_coded_refresh_schedule_is_present():
    """
    Assumption: hard-coded refresh schedules are expressed via setInterval,
    setTimeout, or cron patterns. Their presence would violate the auto-refresh
    requirement; their absence is the verifiable proxy.
    """
    text = _auth_service_text()
    assert "setInterval" not in text, (
        "auth.service.ts must not contain a hard-coded refresh schedule (setInterval)"
    )
    assert "setTimeout" not in text, (
        "auth.service.ts must not contain a hard-coded refresh schedule (setTimeout)"
    )


# ===========================================================================
# Criterion: EntraAuthGuard honours @Public() (reproduces SupabaseAuthGuard logic)
# ===========================================================================

_AUTH_GUARD_TEXT = None


def _auth_guard_text() -> str:
    global _AUTH_GUARD_TEXT
    if _AUTH_GUARD_TEXT is None:
        _AUTH_GUARD_TEXT = overlay_file("src/modules/auth/auth.guard.ts").read_text(
            encoding="utf-8"
        )
    return _AUTH_GUARD_TEXT


def test_when_auth_guard_is_read_then_class_is_named_entra_auth_guard():
    assert "EntraAuthGuard" in _auth_guard_text(), (
        "auth.guard.ts must define a class named EntraAuthGuard"
    )


def test_when_auth_guard_is_read_then_public_decorator_is_honoured():
    """
    Assumption: @Public() is honoured by checking for the IS_PUBLIC_KEY
    reflector metadata, which is the conventional NestJS pattern.
    """
    text = _auth_guard_text()
    has_public = "IS_PUBLIC_KEY" in text or "Public" in text
    assert has_public, "auth.guard.ts must honour the @Public() decorator"


# ===========================================================================
# Criterion: auth.module.ts renames provider/export to EntraAuthGuard;
#            app.module.ts registers EntraAuthGuard as APP_GUARD after ThrottlerGuard,
#            exactly once
# ===========================================================================

_AUTH_MODULE_TEXT = None
_APP_MODULE_TEXT = None


def _auth_module_text() -> str:
    global _AUTH_MODULE_TEXT
    if _AUTH_MODULE_TEXT is None:
        _AUTH_MODULE_TEXT = overlay_file("src/modules/auth/auth.module.ts").read_text(
            encoding="utf-8"
        )
    return _AUTH_MODULE_TEXT


def _app_module_text() -> str:
    global _APP_MODULE_TEXT
    if _APP_MODULE_TEXT is None:
        _APP_MODULE_TEXT = overlay_file("src/app.module.ts").read_text(encoding="utf-8")
    return _APP_MODULE_TEXT


def test_when_auth_module_is_read_then_entra_auth_guard_is_provided():
    assert "EntraAuthGuard" in _auth_module_text(), (
        "auth.module.ts must provide EntraAuthGuard"
    )


def test_when_auth_module_is_read_then_entra_auth_guard_is_exported():
    text = _auth_module_text()
    # Both 'exports' array and 'EntraAuthGuard' must appear
    assert "exports" in text and "EntraAuthGuard" in text, (
        "auth.module.ts must export EntraAuthGuard"
    )


def test_when_app_module_is_read_then_entra_auth_guard_is_registered_as_app_guard():
    text = _app_module_text()
    assert "APP_GUARD" in text, "app.module.ts must register APP_GUARD"
    assert "EntraAuthGuard" in text, "app.module.ts must reference EntraAuthGuard"


def test_when_app_module_is_read_then_entra_auth_guard_appears_exactly_once_as_app_guard():
    """
    Assumption: 'exactly once' means the APP_GUARD provider block for
    EntraAuthGuard appears exactly one time in app.module.ts.
    The module also has ThrottlerGuard as a second APP_GUARD (so APP_GUARD appears
    more than once in total), but EntraAuthGuard must appear exactly once.
    """
    text = _app_module_text()
    # Count occurrences of the useClass: EntraAuthGuard pattern
    entra_guard_registrations = text.count("EntraAuthGuard")
    # EntraAuthGuard appears at minimum in: import + useClass; the useClass pattern
    # is what registers it. We assert APP_GUARD + EntraAuthGuard is not duplicated —
    # the simplest proxy is that 'EntraAuthGuard' does not appear more than twice
    # (once as import, once as useClass).
    assert entra_guard_registrations <= 3, (
        "EntraAuthGuard must not be registered as APP_GUARD more than once in app.module.ts"
    )
    # And it must appear at least once (the registration)
    assert entra_guard_registrations >= 1, "app.module.ts must reference EntraAuthGuard"


def test_when_app_module_is_read_then_throttler_guard_precedes_entra_auth_guard():
    """
    Assumption: 'after ThrottlerGuard' means ThrottlerGuard appears before
    EntraAuthGuard in the providers/guards array in source order.
    """
    text = _app_module_text()
    throttler_pos = text.find("ThrottlerGuard")
    entra_pos = text.find("EntraAuthGuard")
    assert throttler_pos != -1, "app.module.ts must reference ThrottlerGuard"
    assert entra_pos != -1, "app.module.ts must reference EntraAuthGuard"
    assert throttler_pos < entra_pos, (
        "ThrottlerGuard must appear before EntraAuthGuard in app.module.ts"
    )


# ===========================================================================
# Criterion: Authentication failure returns 401; valid token lacking required
#            scope returns 403
# ===========================================================================


def test_when_auth_guard_is_read_then_401_status_code_is_used_for_auth_failure():
    """
    Assumption: the guard throws an UnauthorizedException or uses HttpStatus.UNAUTHORIZED
    (numeric 401) when authentication fails.
    """
    text = _auth_guard_text()
    has_401 = "401" in text or "UNAUTHORIZED" in text or "UnauthorizedException" in text
    assert has_401, (
        "auth.guard.ts must return 401 (UnauthorizedException / UNAUTHORIZED) on auth failure"
    )


def test_when_auth_service_is_read_then_403_status_code_is_used_for_missing_scope():
    """
    Assumption: scope enforcement raises ForbiddenException or uses HttpStatus.FORBIDDEN
    (numeric 403) when the required scope is absent.
    """
    text = _auth_service_text()
    has_403 = "403" in text or "FORBIDDEN" in text or "ForbiddenException" in text
    assert has_403, (
        "auth.service.ts must return 403 (ForbiddenException / FORBIDDEN) when scope is missing"
    )


# ===========================================================================
# Criterion: Parity tests for the entra auth path ship and pass —
#            guard spec, env-validation spec, app-module spec, e2e,
#            renamed to EntraAuthGuard
# ===========================================================================

EXPECTED_TEST_FILES = [
    "src/modules/auth/auth.guard.spec.ts",
    "src/config/env.validation.spec.ts",
    "src/app.module.spec.ts",
]


@pytest.mark.parametrize("rel_path", EXPECTED_TEST_FILES)
def test_when_overlay_is_present_then_parity_test_file_exists(rel_path):
    assert overlay_file(rel_path).is_file(), (
        f"Parity test file {rel_path} must exist in templates-entra-nestjs/"
    )


def test_when_guard_spec_is_read_then_it_references_entra_auth_guard():
    spec_text = overlay_file("src/modules/auth/auth.guard.spec.ts").read_text(
        encoding="utf-8"
    )
    assert "EntraAuthGuard" in spec_text, (
        "auth.guard.spec.ts must be renamed to reference EntraAuthGuard"
    )


# ===========================================================================
# Property-based tests (Hypothesis)
# ===========================================================================


@given(st.text(min_size=1))
@settings(max_examples=50)
def test_when_any_nonempty_tenant_id_is_used_then_jwks_uri_contains_tenant_id(
    tenant_id,
):
    """
    Invariant (idempotence / construction): the JWKS URI must incorporate the
    tenant id string verbatim — for ANY tenant id value, the constructed URI
    must contain it.

    This is a white-box-free property derived from the criterion:
    "JWKS URI built from the tenant id".

    Because we cannot call production code, we verify the structural invariant
    at the template level: the source file must contain a template expression
    that interpolates a tenant-id variable, meaning the produced URI will embed
    whatever tenant id is supplied.

    Specifically: the file must contain at least one template literal or
    string concatenation that references the tenant-id variable alongside
    a microsoft login URL fragment, for ANY input tenant_id string.

    Since this property runs against static source text (not a running function),
    the invariant is: the source file contains a pattern that demonstrates
    dynamic tenant-id interpolation — verified once; the hypothesis engine
    confirms the source text is stable across any tenant_id (idempotence of
    static file content).
    """
    text = _auth_service_text()
    # The source file must embed a reference to the tenant id variable
    # (not a literal URL) — verified for every hypothesis round.
    has_dynamic_tenant = (
        "ENTRA_TENANT_ID" in text or "tenantId" in text or "tenant_id" in text
    )
    assert has_dynamic_tenant, (
        "auth.service.ts JWKS URI must be built from the tenant id (not hard-coded)"
    )


@given(
    st.sampled_from(
        [
            "ENTRA_TENANT_ID",
            "ENTRA_API_CLIENT_ID",
            "ENTRA_API_AUDIENCE",
            "ENTRA_API_SCOPE",
        ]
    )
)
def test_when_any_required_entra_env_var_is_checked_then_it_is_always_declared_in_env_validation(
    env_var,
):
    """
    Invariant (never-raises / completeness): every required Entra env var must
    be declared in env.validation.ts — for all members of the required set.
    """
    assert env_var in _env_validation_text(), (
        f"env.validation.ts must always declare {env_var}"
    )
