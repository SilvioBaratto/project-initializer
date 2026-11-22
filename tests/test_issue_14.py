"""
Source-blind example tests for issue #14: NestJS template hardening.

Tests derived exclusively from the issue #14 acceptance criteria and
.code-generator/requirements.md. Criteria classified [NOT VERIFIABLE] by the oracle
(Terminus health, e2e scaffold, all-tests-pass, SOLID quality) are
intentionally skipped.

Verifiable criteria covered here:
  [UNIT-1] APP_GUARD registered in both the token and supabase overlays
  [UNIT-2] ConfigModule validates env and fails fast on missing secrets
  [UNIT-3] Response schemas whitelist fields (no secret column leaks)
"""

import re
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

# ── Directory constants ────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
PI = REPO_ROOT / "project_initializer"
NESTJS_BASE_API = PI / "templates-api-nestjs" / "api"
NESTJS_TOKEN_API = PI / "templates-token-nestjs" / "api"
NESTJS_SUPABASE_API = PI / "templates-supabase-nestjs" / "api"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _ts_files(*dirs: Path) -> list[Path]:
    files: list[Path] = []
    for d in dirs:
        if d.exists():
            files.extend(d.rglob("*.ts"))
    return files


def _read(path: Path) -> str:
    if not path.exists():
        pytest.fail(f"Required file not found: {path}")
    return path.read_text(encoding="utf-8")


# ── [UNIT-1] APP_GUARD: token overlay ─────────────────────────────────────────


def test_when_token_app_auth_is_read_then_app_guard_is_registered():
    """
    Criterion: the token overlay registers its auth guard as APP_GUARD so routes
    are protected by default; missing this is the biggest security risk.
    Assumption: the root module is shared by all variants, so the overlay supplies its guard
    through `app.auth.ts`, which `app.module.ts` spreads into its providers.

    Validates project_initializer/templates-token-nestjs/api/src/app.auth.ts and project_initializer/templates-api-nestjs/api/src/app.module.ts.
    """
    ts_files = _ts_files(NESTJS_TOKEN_API)
    assert ts_files, "No .ts files found in templates-token-nestjs/api/"

    app_auth = [f for f in ts_files if f.name.lower() == "app.auth.ts"]
    assert app_auth, (
        "No app.auth.ts found in templates-token-nestjs/api/; "
        "the token overlay must provide the seam that registers APP_GUARD"
    )

    content = _read(app_auth[0])
    assert "APP_GUARD" in content, (
        f"APP_GUARD not registered in {app_auth[0]}; "
        "the token auth guard must be a global APP_GUARD provider so all routes are protected"
    )
    assert "...AUTH_GUARDS" in _read(NESTJS_BASE_API / "src" / "app.module.ts"), (
        "base app.module.ts must spread AUTH_GUARDS, or the overlay's guard is never registered"
    )


# ── [UNIT-1] APP_GUARD: supabase overlay ─────────────────────────────────────


def test_when_supabase_app_auth_is_read_then_app_guard_is_registered():
    """
    Criterion: the supabase overlay registers its auth guard as APP_GUARD so routes
    are protected by default.
    Assumption: same seam as the token overlay: `app.auth.ts` supplies the guard provider.

    Validates project_initializer/templates-supabase-nestjs/api/src/app.auth.ts and project_initializer/templates-api-nestjs/api/src/app.module.ts.
    """
    ts_files = _ts_files(NESTJS_SUPABASE_API)
    assert ts_files, "No .ts files found in templates-supabase-nestjs/api/"

    app_auth = [f for f in ts_files if f.name.lower() == "app.auth.ts"]
    assert app_auth, (
        "No app.auth.ts found in templates-supabase-nestjs/api/; "
        "the supabase overlay must provide the seam that registers APP_GUARD"
    )

    content = _read(app_auth[0])
    assert "APP_GUARD" in content, (
        f"APP_GUARD not registered in {app_auth[0]}; "
        "the supabase auth guard must be a global APP_GUARD provider so all routes are protected"
    )
    assert "...AUTH_GUARDS" in _read(NESTJS_BASE_API / "src" / "app.module.ts"), (
        "base app.module.ts must spread AUTH_GUARDS, or the overlay's guard is never registered"
    )


# ── [UNIT-2] ConfigModule: validate function present ──────────────────────────


def test_when_config_module_setup_is_read_then_validate_option_is_present():
    """
    Criterion: ConfigModule validates env and fails fast on missing secrets
    (DATABASE_URL, SUPABASE_*). A `validate` option must be passed to
    ConfigModule.forRoot so startup aborts when required vars are absent.
    Assumption: the validate option appears in a .ts file in the base or any
    auth overlay.

    Validates project_initializer/templates-api-nestjs/api/src/app.module.ts, found among the **/*.ts files of project_initializer/templates-{api,token,supabase}-nestjs/api.
    """
    ts_files = _ts_files(NESTJS_BASE_API, NESTJS_TOKEN_API, NESTJS_SUPABASE_API)
    validate_present = any(
        "ConfigModule" in _read(f) and "validate" in _read(f) for f in ts_files
    )
    assert validate_present, (
        "No .ts file found that passes a `validate` function to ConfigModule; "
        "ConfigModule.forRoot must receive a validate option so startup fails fast "
        "when DATABASE_URL or SUPABASE_* vars are missing"
    )


def test_when_env_validation_schema_is_read_then_required_secrets_are_declared():
    """
    Criterion: the env validation schema declares DATABASE_URL and SUPABASE_* as
    required so the app fails fast on missing secrets.
    Assumption: required var names appear in the same file as the validate logic.

    Validates project_initializer/templates-api-nestjs/api/src/config/env.base.ts and project_initializer/templates-supabase-nestjs/api/src/config/env.validation.ts.
    """
    ts_files = _ts_files(NESTJS_BASE_API, NESTJS_TOKEN_API, NESTJS_SUPABASE_API)

    database_url_found = any("DATABASE_URL" in _read(f) for f in ts_files)
    assert database_url_found, (
        "DATABASE_URL not declared in any .ts file in the NestJS templates; "
        "the env validation schema must list DATABASE_URL as a required secret"
    )

    supabase_found = any(
        re.search(r"SUPABASE_URL|SUPABASE_PUBLISHABLE_KEY", _read(f)) for f in ts_files
    )
    assert supabase_found, (
        "SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY not declared in any .ts file; "
        "the supabase env validation schema must list SUPABASE_* vars as required"
    )


# ── [UNIT-3] Response schemas: no sensitive-column leak ───────────────────────


def test_when_user_response_schema_is_read_then_password_field_is_not_exposed():
    """
    Criterion: response schemas whitelist fields so Prisma rows cannot leak
    sensitive columns (e.g. password) through the StandardSchemaSerializerInterceptor.
    Assumption: at least one response schema or DTO file exists for the User
    entity; it must not expose a `password` field.

    Validates project_initializer/templates-api-nestjs/api/src/common/auth/user-info.dto.ts, found among the user schema and DTO files of project_initializer/templates-{api,token,supabase}-nestjs/api.
    """
    ts_files = _ts_files(NESTJS_BASE_API, NESTJS_TOKEN_API, NESTJS_SUPABASE_API)
    user_schemas = [
        f
        for f in ts_files
        if re.search(r"user", f.name, re.IGNORECASE)
        and re.search(r"schema|dto|response", f.name, re.IGNORECASE)
    ]
    assert user_schemas, (
        "No user response schema/DTO file found in NestJS templates; "
        "a Zod response schema for User must exist to whitelist output fields"
    )

    for schema_file in user_schemas:
        content = _read(schema_file)
        assert not re.search(r"\bpassword\b", content, re.IGNORECASE), (
            f"Response schema {schema_file} exposes a 'password' field; "
            "response schemas must whitelist only safe fields to prevent Prisma row leaks"
        )


# Property-based invariant: across ALL schema/DTO files in every NestJS overlay,
# none may expose a 'password' field.
# Invariant implied by criterion: "response schemas whitelist fields so Prisma
# rows cannot leak secret columns" — this must hold for every schema, not just one.


def _collect_response_schema_files() -> list[Path]:
    # Specs are excluded: they define no schema, and the serialization spec has to name a
    # `password` field to prove that the response schemas strip it.
    return [
        f
        for f in _ts_files(NESTJS_BASE_API, NESTJS_TOKEN_API, NESTJS_SUPABASE_API)
        if re.search(r"schema|dto|response", f.name, re.IGNORECASE)
        and not f.name.endswith(".spec.ts")
    ]


_SCHEMA_FILES = _collect_response_schema_files()

if _SCHEMA_FILES:

    @given(st.sampled_from(_SCHEMA_FILES))
    def test_when_any_response_schema_is_sampled_then_no_password_field_is_exposed(
        schema_file: Path,
    ):
        """
        Invariant: for ALL response schema / DTO files in ALL NestJS template overlays,
        none expose a 'password' field.
        Derived from the criterion: "response schemas whitelist fields so Prisma rows
        cannot leak secret columns through the serializer."

        Validates the schema, DTO and response .ts files, specs excluded, of project_initializer/templates-{api,token,supabase}-nestjs/api.
        """
        content = _read(schema_file)
        assert not re.search(r"\bpassword\b", content, re.IGNORECASE), (
            f"Schema file {schema_file} exposes a 'password' field; "
            "all response schemas must whitelist only safe, non-secret output fields"
        )
else:

    def test_when_any_response_schema_is_sampled_then_no_password_field_is_exposed_fallback():
        pytest.fail(
            "No response schema/DTO files discovered in NestJS templates; "
            "implement the response schemas so this property can be verified"
        )
