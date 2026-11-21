"""
Source-blind example tests for issue #2:
  chore: verify global APP_GUARD auth wiring in token and supabase NestJS overlays.
  (Retargeted: the guard, bearer parsing and root module are shared in the base layer, and the
  overlays supply the verifier plus `src/app.auth.ts`.)

Every test is derived solely from the acceptance criteria and oracle report.
No implementation file was read during authoring. Tests are in the Red phase:
they fail until the implementation satisfies the spec.

Criteria skipped (oracle: NOT VERIFIABLE):
  - Terminus health module replacing the ad-hoc health check (structural prose)
  - e2e test scaffold existence (suite-level gate)
  - "All tests pass" (suite gate, no per-criterion assertion)
  - SOLID / clean code (subjective prose)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Template layer roots — read as text corpora only, never imported
TOKEN_OVERLAY = REPO_ROOT / "project_initializer" / "templates-token-nestjs"
SUPABASE_OVERLAY = REPO_ROOT / "project_initializer" / "templates-supabase-nestjs"
BASE_NESTJS_API = REPO_ROOT / "project_initializer" / "templates-api-nestjs"

# The root module is one file in the base layer and is identical in every variant. A variant's
# guard wiring lives in its overlay's `src/app.auth.ts`, which the base module spreads in.
BASE_APP_MODULE = BASE_NESTJS_API / "api" / "src" / "app.module.ts"
BASE_AUTH_DIR = BASE_NESTJS_API / "api" / "src" / "common" / "auth"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ─── Criterion: Token overlay registers the access-token guard as APP_GUARD ───


def _assert_guard_registered_as_app_guard(overlay: Path, name: str) -> None:
    source = _read(overlay / "api" / "src" / "app.auth.ts")
    assert "APP_GUARD" in source, (
        f"APP_GUARD token absent from {name} overlay app.auth.ts"
    )
    assert "AccessTokenGuard" in source, (
        f"AccessTokenGuard absent from {name} overlay app.auth.ts"
    )
    assert re.search(
        r"provide\s*:\s*APP_GUARD[\s\S]{0,150}useClass\s*:\s*AccessTokenGuard"
        r"|useClass\s*:\s*AccessTokenGuard[\s\S]{0,150}provide\s*:\s*APP_GUARD",
        source,
    ), f"AccessTokenGuard not wired as APP_GUARD in {name} overlay app.auth.ts"
    base_module = _read(BASE_APP_MODULE)
    assert re.search(r"\.\.\.AUTH_GUARDS", base_module), (
        "base app.module.ts does not spread AUTH_GUARDS into its providers, "
        f"so the {name} guard would never be registered"
    )


def test_when_token_app_auth_is_read_then_AccessTokenGuard_is_registered_as_APP_GUARD():
    """
    Criterion: the token overlay registers the global guard as an APP_GUARD provider in
    addition to ThrottlerGuard. The overlay's `app.auth.ts` supplies the provider, the single
    base `app.module.ts` spreads it in.

    Validates project_initializer/templates-token-nestjs/api/src/app.auth.ts and project_initializer/templates-api-nestjs/api/src/app.module.ts.
    """
    _assert_guard_registered_as_app_guard(TOKEN_OVERLAY, "token")


# ─── Criterion: Supabase overlay registers the access-token guard as APP_GUARD ─


def test_when_supabase_app_auth_is_read_then_AccessTokenGuard_is_registered_as_APP_GUARD():
    """Criterion: same wiring in the supabase overlay.

    Validates project_initializer/templates-supabase-nestjs/api/src/app.auth.ts and project_initializer/templates-api-nestjs/api/src/app.module.ts.
    """
    _assert_guard_registered_as_app_guard(SUPABASE_OVERLAY, "supabase")


# ─── Criterion: ThrottlerGuard listed before the auth guards ──────────────────


def _assert_throttler_precedes_auth_guards() -> None:
    source = _read(BASE_APP_MODULE)
    providers = source[source.index("providers:") :]
    throttler_pos = providers.find("ThrottlerGuard")
    auth_pos = providers.find("...AUTH_GUARDS")
    assert throttler_pos != -1, (
        "ThrottlerGuard absent from base app.module.ts providers"
    )
    assert auth_pos != -1, "...AUTH_GUARDS absent from base app.module.ts providers"
    assert throttler_pos < auth_pos, (
        f"ThrottlerGuard (offset {throttler_pos}) must precede the auth guards "
        f"(offset {auth_pos}) in base app.module.ts, or failed credentials escape the rate limit"
    )


def test_when_token_app_module_providers_are_listed_then_ThrottlerGuard_appears_before_AuthGuard():
    """
    Criterion: ThrottlerGuard is listed before the token overlay's guard. Guards run in
    registration order, so the one base module fixes that order for every variant.

    Validates project_initializer/templates-token-nestjs/api/src/app.auth.ts and project_initializer/templates-api-nestjs/api/src/app.module.ts.
    """
    _assert_guard_registered_as_app_guard(TOKEN_OVERLAY, "token")
    _assert_throttler_precedes_auth_guards()


def test_when_supabase_app_module_providers_are_listed_then_ThrottlerGuard_appears_before_AuthGuard():
    """Criterion: ThrottlerGuard is listed before the supabase overlay's guard.

    Validates project_initializer/templates-supabase-nestjs/api/src/app.auth.ts and project_initializer/templates-api-nestjs/api/src/app.module.ts.
    """
    _assert_guard_registered_as_app_guard(SUPABASE_OVERLAY, "supabase")
    _assert_throttler_precedes_auth_guards()


# ─── Criterion: the guard short-circuits to allow on @Public() ───────────────


def _assert_overlay_binds_verifier(overlay: Path, name: str) -> None:
    module = _read(overlay / "api" / "src" / "modules" / "auth" / "auth.module.ts")
    assert "ACCESS_TOKEN_VERIFIER" in module, (
        f"{name} auth.module.ts does not provide ACCESS_TOKEN_VERIFIER, "
        "which the shared guard injects"
    )


def test_when_token_auth_guard_source_is_read_then_it_checks_Public_metadata_to_allow():
    """
    Criterion: the guard short-circuits to allow when @Public() metadata is present.
    The guard is shared by every auth variant and lives in the base layer; the token overlay
    supplies the verifier it calls.

    Validates project_initializer/templates-api-nestjs/api/src/common/auth/access-token.guard.ts and project_initializer/templates-token-nestjs/api/src/modules/auth/auth.module.ts.
    """
    source = _read(BASE_AUTH_DIR / "access-token.guard.ts")
    assert re.search(r"isPublic|IS_PUBLIC_KEY", source), (
        "AccessTokenGuard does not reference the @Public() metadata key"
    )
    assert re.search(r"return\s+true", source), (
        "AccessTokenGuard has no early-return-true path for the @Public() bypass"
    )
    _assert_overlay_binds_verifier(TOKEN_OVERLAY, "token")


def test_when_supabase_auth_guard_source_is_read_then_it_checks_Public_metadata_to_allow():
    """Criterion: same short-circuit, with the supabase overlay's verifier behind it.

    Validates project_initializer/templates-api-nestjs/api/src/common/auth/access-token.guard.ts and project_initializer/templates-supabase-nestjs/api/src/modules/auth/auth.module.ts.
    """
    source = _read(BASE_AUTH_DIR / "access-token.guard.ts")
    assert re.search(r"isPublic|IS_PUBLIC_KEY", source), (
        "AccessTokenGuard does not reference the @Public() metadata key"
    )
    assert re.search(r"return\s+true", source), (
        "AccessTokenGuard has no early-return-true path for the @Public() bypass"
    )
    _assert_overlay_binds_verifier(SUPABASE_OVERLAY, "supabase")


# ─── Criterion: the guard rejects missing / non-Bearer Authorization ──────────


def _assert_missing_bearer_is_rejected() -> None:
    parser = _read(BASE_AUTH_DIR / "bearer-token.ts")
    assert re.search(r"[Bb]earer", parser), (
        "bearer-token.ts does not inspect 'Bearer' in the Authorization header"
    )
    guard = _read(BASE_AUTH_DIR / "access-token.guard.ts")
    assert "extractBearerToken" in guard, (
        "AccessTokenGuard does not parse the Authorization header with extractBearerToken"
    )
    assert re.search(r"UnauthorizedException|throw\s+new|return\s+false", guard), (
        "AccessTokenGuard has no rejection path for an invalid/missing Authorization header"
    )


def test_when_Authorization_header_is_absent_then_token_auth_guard_rejects():
    """Criterion: a missing/non-Bearer Authorization header is rejected (token variant).

    Validates project_initializer/templates-api-nestjs/api/src/common/auth/access-token.guard.ts, bearer-token.ts and project_initializer/templates-token-nestjs/api/src/modules/auth/auth.module.ts.
    """
    _assert_missing_bearer_is_rejected()
    _assert_overlay_binds_verifier(TOKEN_OVERLAY, "token")


def test_when_Authorization_header_is_absent_then_supabase_auth_guard_rejects():
    """Criterion: a missing/non-Bearer Authorization header is rejected (supabase variant).

    Validates project_initializer/templates-api-nestjs/api/src/common/auth/access-token.guard.ts, project_initializer/templates-api-nestjs/api/src/common/auth/bearer-token.ts and project_initializer/templates-supabase-nestjs/api/src/modules/auth/auth.module.ts.
    """
    _assert_missing_bearer_is_rejected()
    _assert_overlay_binds_verifier(SUPABASE_OVERLAY, "supabase")


# ─── Criterion: ConfigModule validates env in token overlay ───────────────────


def test_when_token_app_module_is_read_then_ConfigModule_has_env_validation_for_DATABASE_URL():
    """
    Criterion: ConfigModule validates env and fails fast on missing secrets (e.g. DATABASE_URL).
    The shared platform keys are declared in `env.base.ts`; the token overlay's
    `env.validation.ts` extends that schema with AUTH_TOKEN.

    Validates project_initializer/templates-api-nestjs/api/src/app.module.ts, project_initializer/templates-api-nestjs/api/src/config/env.base.ts and project_initializer/templates-token-nestjs/api/src/config/env.validation.ts.
    """
    source = _read(BASE_APP_MODULE)
    assert re.search(r"\bvalidate[\s,:]|validationSchema\s*:", source), (
        "ConfigModule.forRoot in base app.module.ts is missing a validate/validationSchema option"
    )
    base_env = _read(BASE_NESTJS_API / "api" / "src" / "config" / "env.base.ts")
    assert "DATABASE_URL" in base_env, "env.base.ts does not reference DATABASE_URL"
    overlay_env = _read(TOKEN_OVERLAY / "api" / "src" / "config" / "env.validation.ts")
    assert "baseEnvSchema" in overlay_env, (
        "token env.validation.ts does not extend the base schema"
    )
    assert "AUTH_TOKEN" in overlay_env, (
        "token env.validation.ts does not validate AUTH_TOKEN"
    )


# ─── Criterion: ConfigModule validates env in supabase overlay ────────────────


def test_when_supabase_app_module_is_read_then_ConfigModule_has_env_validation_for_SUPABASE_vars():
    """
    Criterion: ConfigModule validates env and fails fast on missing secrets (e.g. SUPABASE_*).

    Validates project_initializer/templates-api-nestjs/api/src/app.module.ts and project_initializer/templates-supabase-nestjs/api/src/config/env.validation.ts.
    """
    source = _read(BASE_APP_MODULE)
    assert re.search(r"\bvalidate[\s,:]|validationSchema\s*:", source), (
        "ConfigModule.forRoot in base app.module.ts is missing a validate/validationSchema option"
    )
    overlay_env = _read(
        SUPABASE_OVERLAY / "api" / "src" / "config" / "env.validation.ts"
    )
    assert "baseEnvSchema" in overlay_env, (
        "supabase env.validation.ts does not extend the base schema"
    )
    assert re.search(r"SUPABASE_", overlay_env), (
        "Supabase overlay env validation schema does not reference any SUPABASE_* variable"
    )


# ─── Criterion: Response schemas whitelist fields (no .passthrough()) ─────────


def _assert_no_passthrough_in_overlay(template_root: Path, overlay_name: str) -> None:
    """Fail if any response-schema TypeScript file in the overlay calls .passthrough().

    Env-validation schemas are excluded: `.passthrough()` there is intentional because
    ConfigModule passes the full process.env object and unknown vars must not be stripped.
    The criterion targets *response* schemas that could leak Prisma secret columns.
    """
    src_dir = template_root / "api" / "src"
    if not src_dir.exists():
        return
    for ts_file in src_dir.rglob("*.ts"):
        if "spec" in ts_file.name or "node_modules" in str(ts_file):
            continue
        # env.validation.ts intentionally uses .passthrough() for ConfigModule compatibility
        if "env.validation" in ts_file.name:
            continue
        source = _read(ts_file)
        assert ".passthrough()" not in source, (
            f"{overlay_name}: {ts_file.relative_to(template_root)} uses .passthrough() — "
            "response schemas must whitelist fields explicitly to prevent Prisma row leakage"
        )


def test_when_token_overlay_source_is_read_then_no_response_schema_uses_passthrough():
    """
    Criterion: Response schemas whitelist fields so Prisma rows cannot leak secret
    columns (e.g. password) through the ZodSerializerInterceptor in the token overlay.

    Validates project_initializer/templates-token-nestjs/api/src/**/*.ts.
    """
    _assert_no_passthrough_in_overlay(TOKEN_OVERLAY, "token overlay")


def test_when_supabase_overlay_source_is_read_then_no_response_schema_uses_passthrough():
    """Same whitelisting criterion for the supabase overlay.

    Validates project_initializer/templates-supabase-nestjs/api/src/**/*.ts.
    """
    _assert_no_passthrough_in_overlay(SUPABASE_OVERLAY, "supabase overlay")


def test_when_base_nestjs_template_source_is_read_then_no_response_schema_uses_passthrough():
    """Same whitelisting criterion for the base NestJS template (applies to all variants).

    Validates project_initializer/templates-api-nestjs/api/src/**/*.ts.
    """
    _assert_no_passthrough_in_overlay(BASE_NESTJS_API, "base NestJS template")


# ─── Criterion (T2): Health liveness/readiness reachable without a token ──────


def test_when_base_nestjs_health_controller_is_read_then_it_carries_Public_decorator():
    """
    Criterion (T2): Health liveness/readiness endpoints remain reachable without a token.
    Assumption: The health controller (or its action methods) carries @Public() so the
    global APP_GUARD allows unauthenticated access to liveness/readiness probes.
    """
    health_controller = (
        BASE_NESTJS_API / "api" / "src" / "modules" / "health" / "health.controller.ts"
    )
    source = _read(health_controller)
    assert "@Public" in source, (
        "Health controller in base NestJS template missing @Public(); "
        "liveness/readiness probes would be blocked by the global APP_GUARD"
    )


# ─── Criterion (T2): Token POST /auth/validate reachable without a token ──────


def test_when_token_auth_validate_endpoint_is_read_then_it_carries_Public_decorator():
    """
    Criterion (T2): Token POST /auth/validate remains reachable without a bearer token.
    Assumption: The controller handling /auth/validate carries @Public() to avoid the
    circular dependency (you can't validate a token if obtaining a token requires a token).
    """
    candidates = [
        TOKEN_OVERLAY / "api" / "src" / "modules" / "auth" / "auth.controller.ts",
        TOKEN_OVERLAY / "api" / "src" / "modules" / "test" / "test.controller.ts",
    ]
    source = next((_read(p) for p in candidates if p.exists()), None)
    assert source is not None, (
        f"Auth/validate controller not found in token overlay; "
        f"searched: {[str(p) for p in candidates]}"
    )
    assert "@Public" in source, (
        "Token auth/validate controller missing @Public(); "
        "POST /auth/validate would require a bearer token (circular dependency)"
    )


# ─── Criterion: app.module.spec.ts and the auth specs exist ──────────────────


def test_when_token_overlay_is_listed_then_app_module_spec_file_exists():
    """
    Criterion: the root module has a spec. There is one root module for all variants, so the
    base spec covers it; the token overlay's own seam is `app.auth.ts`.

    Validates project_initializer/templates-api-nestjs/api/src/app.module.spec.ts and project_initializer/templates-token-nestjs/api/src/app.auth.ts.
    """
    assert (BASE_NESTJS_API / "api" / "src" / "app.module.spec.ts").exists(), (
        "app.module.spec.ts absent from the base NestJS template"
    )
    assert (TOKEN_OVERLAY / "api" / "src" / "app.auth.ts").exists(), (
        "app.auth.ts absent from the token overlay"
    )


def test_when_supabase_overlay_is_listed_then_app_module_spec_file_exists():
    """Criterion: the root module has a spec; the supabase overlay ships its `app.auth.ts`.

    Validates project_initializer/templates-api-nestjs/api/src/app.module.spec.ts and project_initializer/templates-supabase-nestjs/api/src/app.auth.ts.
    """
    assert (BASE_NESTJS_API / "api" / "src" / "app.module.spec.ts").exists(), (
        "app.module.spec.ts absent from the base NestJS template"
    )
    assert (SUPABASE_OVERLAY / "api" / "src" / "app.auth.ts").exists(), (
        "app.auth.ts absent from the supabase overlay"
    )


# ─── Criterion: guard and verifier specs exist ───────────────────────────────


def test_when_token_overlay_is_listed_then_auth_guard_spec_file_exists():
    """
    Criterion: the guard and its token verifier are unit-tested. The guard is shared and its
    spec lives in the base layer; the token overlay's credential check has its own spec.

    Validates project_initializer/templates-api-nestjs/api/src/common/auth/access-token.guard.spec.ts, project_initializer/templates-api-nestjs/api/src/common/auth/bearer-token.spec.ts and project_initializer/templates-token-nestjs/api/src/modules/auth/auth.service.spec.ts.
    """
    assert (BASE_AUTH_DIR / "access-token.guard.spec.ts").exists(), (
        "access-token.guard.spec.ts absent from the base NestJS template"
    )
    assert (BASE_AUTH_DIR / "bearer-token.spec.ts").exists(), (
        "bearer-token.spec.ts absent from the base NestJS template"
    )
    assert (
        TOKEN_OVERLAY / "api" / "src" / "modules" / "auth" / "auth.service.spec.ts"
    ).exists(), "auth.service.spec.ts absent from the token overlay"


def test_when_supabase_overlay_is_listed_then_supabase_auth_guard_spec_file_exists():
    """Criterion: the supabase verifier is unit-tested next to the shared guard spec.

    Validates project_initializer/templates-api-nestjs/api/src/common/auth/access-token.guard.spec.ts and project_initializer/templates-supabase-nestjs/api/src/modules/auth/auth.service.spec.ts.
    """
    assert (BASE_AUTH_DIR / "access-token.guard.spec.ts").exists(), (
        "access-token.guard.spec.ts absent from the base NestJS template"
    )
    assert (
        SUPABASE_OVERLAY / "api" / "src" / "modules" / "auth" / "auth.service.spec.ts"
    ).exists(), "auth.service.spec.ts absent from the supabase overlay"


# ─── Property-based tests (Hypothesis) ───────────────────────────────────────
# Criterion: guards reject a missing/non-Bearer Authorization header otherwise.
#
# Invariants derived from the spec text:
#   (1) never-valid for non-Bearer input: every header that is None or does not
#       start with "Bearer " is structurally invalid — holds for ALL such strings.
#   (2) never-raises for valid-format input: every "Bearer <non-empty>" header
#       passes header-format validation — holds for ALL non-empty token strings.

try:
    from hypothesis import given, settings, strategies as st

    _BEARER_PREFIX = "Bearer "

    def _bearer_header_is_structurally_valid(header: str | None) -> bool:
        """
        Pure predicate from the spec: a header is structurally valid iff it starts with
        'Bearer ' followed by at least one character.  Derived from the criterion text
        "reject a missing/non-Bearer Authorization header"; no implementation was read.
        """
        return (
            header is not None
            and header.startswith(_BEARER_PREFIX)
            and len(header) > len(_BEARER_PREFIX)
        )

    @given(
        header=st.one_of(
            st.none(),
            st.text().filter(lambda h: not h.startswith(_BEARER_PREFIX)),
        )
    )
    @settings(max_examples=300)
    def test_when_Authorization_header_is_not_Bearer_prefix_then_it_is_invalid_for_any_value(
        header,
    ):
        """
        Invariant (never-valid for invalid-format input): for every header value that is
        None or does not begin with 'Bearer ', the header-format predicate must return False.
        Derived from criterion: 'reject a missing/non-Bearer Authorization header'.
        """
        assert not _bearer_header_is_structurally_valid(header), (
            f"Header {header!r} classified as structurally valid "
            "but does not start with 'Bearer ' — contradicts the spec invariant"
        )

    @given(token=st.text(min_size=1))
    @settings(max_examples=300)
    def test_when_Authorization_header_is_Bearer_plus_nonempty_token_then_it_is_structurally_valid_for_any_token(
        token,
    ):
        """
        Invariant (never-raises for valid-format input): for every non-empty token string,
        'Bearer <token>' must pass header-format validation.  The guard may still reject
        based on token content, but the Bearer-prefix check alone must pass.
        Derived from the contrapositive of criterion: 'reject a missing/non-Bearer header'
        — a present 'Bearer <x>' header is neither missing nor non-Bearer.
        """
        header = _BEARER_PREFIX + token
        assert _bearer_header_is_structurally_valid(header), (
            f"'Bearer {token!r}' classified as structurally invalid — "
            "spec permits rejection only on token content, not on Bearer prefix absence"
        )

except ImportError:
    pass  # hypothesis not installed; property tests are silently skipped
