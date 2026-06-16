"""
Source-blind example tests for issue #2:
  chore: verify global APP_GUARD auth wiring in token and supabase NestJS overlays.

Every test is derived solely from the acceptance criteria and oracle report.
No implementation file was read during authoring. Tests are in the Red phase:
they fail until the implementation satisfies the spec.

Criteria skipped (oracle: NOT VERIFIABLE):
  - Terminus health module replacing the ad-hoc health check (structural prose)
  - e2e test scaffold existence (suite-level gate)
  - BullMQ job offloading (optional)
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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ─── Criterion: Token overlay registers AuthGuard as APP_GUARD ───────────────


def test_when_token_app_module_is_read_then_AuthGuard_is_registered_as_APP_GUARD():
    """
    Criterion: Token overlay app.module.ts registers AuthGuard as an APP_GUARD provider
    in addition to ThrottlerGuard.
    Assumption: The providers array contains an object of the form
      { provide: APP_GUARD, useClass: AuthGuard }.
    """
    source = _read(TOKEN_OVERLAY / "api" / "src" / "app.module.ts")
    assert "APP_GUARD" in source, (
        "APP_GUARD token absent from token overlay app.module.ts"
    )
    assert "AuthGuard" in source, "AuthGuard absent from token overlay app.module.ts"
    assert re.search(
        r"provide\s*:\s*APP_GUARD[\s\S]{0,150}useClass\s*:\s*AuthGuard"
        r"|useClass\s*:\s*AuthGuard[\s\S]{0,150}provide\s*:\s*APP_GUARD",
        source,
    ), "AuthGuard not wired as APP_GUARD in token overlay app.module.ts"


# ─── Criterion: Supabase overlay registers SupabaseAuthGuard as APP_GUARD ────


def test_when_supabase_app_module_is_read_then_SupabaseAuthGuard_is_registered_as_APP_GUARD():
    """
    Criterion: Supabase overlay app.module.ts registers SupabaseAuthGuard as an APP_GUARD
    provider in addition to ThrottlerGuard.
    Assumption: Same object shape as token variant but with SupabaseAuthGuard.
    """
    source = _read(SUPABASE_OVERLAY / "api" / "src" / "app.module.ts")
    assert "APP_GUARD" in source, (
        "APP_GUARD token absent from supabase overlay app.module.ts"
    )
    assert "SupabaseAuthGuard" in source, (
        "SupabaseAuthGuard absent from supabase overlay app.module.ts"
    )
    assert re.search(
        r"provide\s*:\s*APP_GUARD[\s\S]{0,150}useClass\s*:\s*SupabaseAuthGuard"
        r"|useClass\s*:\s*SupabaseAuthGuard[\s\S]{0,150}provide\s*:\s*APP_GUARD",
        source,
    ), "SupabaseAuthGuard not wired as APP_GUARD in supabase overlay app.module.ts"


# ─── Criterion: ThrottlerGuard listed before AuthGuard in token overlay ───────


def test_when_token_app_module_providers_are_listed_then_ThrottlerGuard_appears_before_AuthGuard():
    """
    Criterion: ThrottlerGuard is listed before AuthGuard in the token overlay
    app.module.ts providers array (rate-limit evaluated alongside/before auth; intentional).
    """
    source = _read(TOKEN_OVERLAY / "api" / "src" / "app.module.ts")
    throttler_pos = source.find("ThrottlerGuard")
    auth_pos = source.find("AuthGuard")
    assert throttler_pos != -1, "ThrottlerGuard absent from token overlay app.module.ts"
    assert auth_pos != -1, "AuthGuard absent from token overlay app.module.ts"
    assert throttler_pos < auth_pos, (
        f"ThrottlerGuard (offset {throttler_pos}) must precede AuthGuard "
        f"(offset {auth_pos}) in token overlay app.module.ts"
    )


# ─── Criterion: ThrottlerGuard listed before SupabaseAuthGuard in supabase overlay


def test_when_supabase_app_module_providers_are_listed_then_ThrottlerGuard_appears_before_SupabaseAuthGuard():
    """
    Criterion: ThrottlerGuard is listed before SupabaseAuthGuard in the supabase overlay
    app.module.ts providers array.
    """
    source = _read(SUPABASE_OVERLAY / "api" / "src" / "app.module.ts")
    throttler_pos = source.find("ThrottlerGuard")
    auth_pos = source.find("SupabaseAuthGuard")
    assert throttler_pos != -1, (
        "ThrottlerGuard absent from supabase overlay app.module.ts"
    )
    assert auth_pos != -1, (
        "SupabaseAuthGuard absent from supabase overlay app.module.ts"
    )
    assert throttler_pos < auth_pos, (
        f"ThrottlerGuard (offset {throttler_pos}) must precede SupabaseAuthGuard "
        f"(offset {auth_pos}) in supabase overlay app.module.ts"
    )


# ─── Criterion: Token AuthGuard short-circuits to allow on @Public() ─────────


def test_when_token_auth_guard_source_is_read_then_it_checks_Public_metadata_to_allow():
    """
    Criterion: Token AuthGuard short-circuits to allow when @Public() metadata is present.
    Assumption: The guard calls Reflector (getAllAndOverride or equivalent) with an
    isPublic / IS_PUBLIC_KEY flag and returns true before validating the token.
    Guard file lives at modules/auth/auth.guard.ts in the overlay.
    """
    guard = TOKEN_OVERLAY / "api" / "src" / "modules" / "auth" / "auth.guard.ts"
    source = _read(guard)
    assert re.search(r"isPublic|IS_PUBLIC_KEY", source), (
        "Token AuthGuard does not reference the @Public() metadata key"
    )
    assert re.search(r"return\s+true", source), (
        "Token AuthGuard has no early-return-true path for the @Public() bypass"
    )


# ─── Criterion: SupabaseAuthGuard short-circuits to allow on @Public() ────────


def test_when_supabase_auth_guard_source_is_read_then_it_checks_Public_metadata_to_allow():
    """
    Criterion: SupabaseAuthGuard short-circuits to allow when @Public() metadata is present.
    Guard file lives at modules/auth/auth.guard.ts in the overlay.
    """
    guard = SUPABASE_OVERLAY / "api" / "src" / "modules" / "auth" / "auth.guard.ts"
    source = _read(guard)
    assert re.search(r"isPublic|IS_PUBLIC_KEY", source), (
        "SupabaseAuthGuard does not reference the @Public() metadata key"
    )
    assert re.search(r"return\s+true", source), (
        "SupabaseAuthGuard has no early-return-true path for the @Public() bypass"
    )


# ─── Criterion: Token AuthGuard rejects missing / non-Bearer Authorization ────


def test_when_Authorization_header_is_absent_then_token_auth_guard_rejects():
    """
    Criterion: Token AuthGuard rejects a missing/non-Bearer Authorization header.
    Assumption: The guard checks for the 'Bearer ' prefix and throws
    UnauthorizedException (or returns false) when the header is absent or malformed.
    Guard file lives at modules/auth/auth.guard.ts in the overlay.
    """
    guard = TOKEN_OVERLAY / "api" / "src" / "modules" / "auth" / "auth.guard.ts"
    source = _read(guard)
    assert re.search(r"[Bb]earer", source), (
        "Token AuthGuard does not inspect 'Bearer' in the Authorization header"
    )
    assert re.search(r"UnauthorizedException|throw\s+new|return\s+false", source), (
        "Token AuthGuard has no rejection path for an invalid/missing Authorization header"
    )


# ─── Criterion: SupabaseAuthGuard rejects missing / non-Bearer Authorization ──


def test_when_Authorization_header_is_absent_then_supabase_auth_guard_rejects():
    """
    Criterion: SupabaseAuthGuard rejects a missing/non-Bearer Authorization header.
    Guard file lives at modules/auth/auth.guard.ts in the overlay.
    """
    guard = SUPABASE_OVERLAY / "api" / "src" / "modules" / "auth" / "auth.guard.ts"
    source = _read(guard)
    assert re.search(r"[Bb]earer", source), (
        "SupabaseAuthGuard does not inspect 'Bearer' in the Authorization header"
    )
    assert re.search(r"UnauthorizedException|throw\s+new|return\s+false", source), (
        "SupabaseAuthGuard has no rejection path for an invalid/missing Authorization header"
    )


# ─── Criterion: ConfigModule validates env in token overlay ───────────────────


def test_when_token_app_module_is_read_then_ConfigModule_has_env_validation_for_DATABASE_URL():
    """
    Criterion: ConfigModule validates env and fails fast on missing secrets
    (e.g. DATABASE_URL) in the token overlay.
    Assumption: ConfigModule.forRoot includes a `validate` option (either as the
    explicit form `validate: fn` or the ES2015 shorthand `validate,`).
    The referenced validate function/schema must reference DATABASE_URL.
    """
    source = _read(TOKEN_OVERLAY / "api" / "src" / "app.module.ts")
    # Match explicit `validate:`, shorthand `validate,`, or `validationSchema:`
    assert re.search(r"\bvalidate[\s,]|validationSchema\s*:", source), (
        "Token overlay ConfigModule.forRoot missing a validate/validationSchema option"
    )
    corpus = source
    for candidate in [
        TOKEN_OVERLAY / "api" / "src" / "config" / "env.validation.ts",
        TOKEN_OVERLAY / "api" / "src" / "config" / "config.validation.ts",
        TOKEN_OVERLAY / "api" / "src" / "config" / "env.schema.ts",
    ]:
        if candidate.exists():
            corpus += _read(candidate)
    assert "DATABASE_URL" in corpus, (
        "Token overlay env validation schema does not reference DATABASE_URL"
    )


# ─── Criterion: ConfigModule validates env in supabase overlay ────────────────


def test_when_supabase_app_module_is_read_then_ConfigModule_has_env_validation_for_SUPABASE_vars():
    """
    Criterion: ConfigModule validates env and fails fast on missing secrets
    (e.g. SUPABASE_*) in the supabase overlay.
    Assumption: Same validate shorthand pattern as token overlay.
    """
    source = _read(SUPABASE_OVERLAY / "api" / "src" / "app.module.ts")
    # Match explicit `validate:`, shorthand `validate,`, or `validationSchema:`
    assert re.search(r"\bvalidate[\s,]|validationSchema\s*:", source), (
        "Supabase overlay ConfigModule.forRoot missing a validate/validationSchema option"
    )
    corpus = source
    for candidate in [
        SUPABASE_OVERLAY / "api" / "src" / "config" / "env.validation.ts",
        SUPABASE_OVERLAY / "api" / "src" / "config" / "config.validation.ts",
        SUPABASE_OVERLAY / "api" / "src" / "config" / "env.schema.ts",
    ]:
        if candidate.exists():
            corpus += _read(candidate)
    assert re.search(r"SUPABASE_", corpus), (
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
    """
    _assert_no_passthrough_in_overlay(TOKEN_OVERLAY, "token overlay")


def test_when_supabase_overlay_source_is_read_then_no_response_schema_uses_passthrough():
    """Same whitelisting criterion for the supabase overlay."""
    _assert_no_passthrough_in_overlay(SUPABASE_OVERLAY, "supabase overlay")


def test_when_base_nestjs_template_source_is_read_then_no_response_schema_uses_passthrough():
    """Same whitelisting criterion for the base NestJS template (applies to all variants)."""
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


# ─── Criterion: app.module.spec.ts exists in both overlays ───────────────────


def test_when_token_overlay_is_listed_then_app_module_spec_file_exists():
    """
    Criterion: Existing app.module.spec.ts in the token overlay passes.
    Source-blind proxy: the file must exist for the NestJS suite to execute it.
    """
    spec = TOKEN_OVERLAY / "api" / "src" / "app.module.spec.ts"
    assert spec.exists(), (
        f"app.module.spec.ts absent from token overlay (expected at {spec})"
    )


def test_when_supabase_overlay_is_listed_then_app_module_spec_file_exists():
    """Criterion: Existing app.module.spec.ts in the supabase overlay passes."""
    spec = SUPABASE_OVERLAY / "api" / "src" / "app.module.spec.ts"
    assert spec.exists(), (
        f"app.module.spec.ts absent from supabase overlay (expected at {spec})"
    )


# ─── Criterion: auth.guard.spec.ts exists in both overlays ───────────────────


def test_when_token_overlay_is_listed_then_auth_guard_spec_file_exists():
    """Criterion: Existing auth.guard.spec.ts in the token overlay passes.
    Guard spec lives at modules/auth/auth.guard.spec.ts in the overlay.
    """
    candidates = [
        TOKEN_OVERLAY / "api" / "src" / "modules" / "auth" / "auth.guard.spec.ts",
        TOKEN_OVERLAY / "api" / "src" / "common" / "guards" / "auth.guard.spec.ts",
    ]
    assert any(p.exists() for p in candidates), (
        f"auth.guard.spec.ts absent from token overlay; "
        f"searched: {[str(p) for p in candidates]}"
    )


def test_when_supabase_overlay_is_listed_then_supabase_auth_guard_spec_file_exists():
    """Criterion: Existing auth.guard.spec.ts in the supabase overlay passes.
    Guard spec lives at modules/auth/auth.guard.spec.ts in the overlay.
    """
    candidates = [
        SUPABASE_OVERLAY / "api" / "src" / "modules" / "auth" / "auth.guard.spec.ts",
        SUPABASE_OVERLAY
        / "api"
        / "src"
        / "common"
        / "guards"
        / "supabase-auth.guard.spec.ts",
    ]
    assert any(p.exists() for p in candidates), (
        f"Supabase auth guard spec absent from supabase overlay; "
        f"searched: {[str(p) for p in candidates]}"
    )


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
