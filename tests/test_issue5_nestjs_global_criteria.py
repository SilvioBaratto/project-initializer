"""
Source-blind example tests for issue #5 global acceptance criteria (UNIT-verifiable).

Tests parse NestJS TypeScript template files as plain text; they never import or execute
production source. All assertions are derived from the acceptance-criteria text only.

Criteria under test:
  [UNIT] Auth guard registered as APP_GUARD in both token and supabase overlays.
  [UNIT] ConfigModule validates env and fails fast on missing secrets.
  [UNIT] Response schemas whitelist fields so Prisma rows cannot leak secret columns.
"""

import pathlib
import re

import pytest
from hypothesis import given, strategies as st

REPO_ROOT = pathlib.Path(__file__).parent.parent
PI = REPO_ROOT / "project_initializer"

# Auth overlay app-module files
AUTH_APP_MODULES = [
    PI / "templates-token-nestjs" / "api" / "src" / "app.module.ts",
    PI / "templates-supabase-nestjs" / "api" / "src" / "app.module.ts",
]

# ConfigModule definition — base or overlays share the config setup
CONFIG_MODULE_FILES = [
    PI / "templates-api-nestjs" / "api" / "src" / "app.module.ts",
    PI / "templates-token-nestjs" / "api" / "src" / "app.module.ts",
    PI / "templates-supabase-nestjs" / "api" / "src" / "app.module.ts",
]

# Response DTO files (contain Zod schemas wrapping Prisma model data).
# NestJS templates use *.dto.ts (not *.schema.ts) for DTO/schema definitions.
SCHEMA_FILES_TOKEN = list(
    (PI / "templates-token-nestjs" / "api" / "src").rglob("*.dto.ts")
)
SCHEMA_FILES_SUPABASE = list(
    (PI / "templates-supabase-nestjs" / "api" / "src").rglob("*.dto.ts")
)
SCHEMA_FILES_BASE = list(
    (PI / "templates-api-nestjs" / "api" / "src").rglob("*.dto.ts")
)
ALL_RESPONSE_SCHEMA_FILES = (
    SCHEMA_FILES_BASE + SCHEMA_FILES_TOKEN + SCHEMA_FILES_SUPABASE
)


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Criterion 1: Auth guard registered as APP_GUARD in token and supabase overlays
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module_path", AUTH_APP_MODULES, ids=lambda p: p.parts[-4])
def test_when_auth_overlay_app_module_is_read_then_app_guard_provider_is_present(
    module_path,
):
    """Criterion: token and supabase overlay app modules register their auth guard as APP_GUARD.

    Assumption: 'registered as APP_GUARD' means the providers array contains an object
    with `provide: APP_GUARD` (the standard NestJS global-guard pattern).
    """
    source = read_text(module_path)
    assert "APP_GUARD" in source, (
        f"APP_GUARD not found in {module_path}; auth guard must be global"
    )


@pytest.mark.parametrize("module_path", AUTH_APP_MODULES, ids=lambda p: p.parts[-4])
def test_when_auth_overlay_app_module_is_read_then_auth_guard_class_is_provided_as_app_guard(
    module_path,
):
    """Criterion: the guard class wired to APP_GUARD is the variant's auth guard, not a different class.

    Assumption: the useClass value in the APP_GUARD provider must reference a class whose name
    contains 'AuthGuard' or 'Guard' (both 'AuthGuard' and 'SupabaseAuthGuard' qualify).
    """
    source = read_text(module_path)
    # Look for { provide: APP_GUARD, useClass: <SomethingGuard> } (whitespace-tolerant)
    pattern = re.compile(
        r"provide\s*:\s*APP_GUARD[\s\S]{0,200}?useClass\s*:\s*(\w+Guard)",
        re.DOTALL,
    )
    match = pattern.search(source)
    assert match is not None, (
        f"No '{{ provide: APP_GUARD, useClass: <...Guard> }}' pattern found in {module_path}"
    )


# ---------------------------------------------------------------------------
# Criterion 2: ConfigModule validates env and fails fast on missing secrets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module_path", CONFIG_MODULE_FILES, ids=lambda p: p.parts[-4])
def test_when_app_module_is_read_then_config_module_uses_validate_option(module_path):
    """Criterion: ConfigModule is configured with a validate function for env-var validation.

    Assumption: NestJS ConfigModule accepts a `validate` option (or a `validationSchema`
    in older patterns). We accept either `validate:` or `validationSchema:` as evidence.
    """
    source = read_text(module_path)
    has_validate = "validate:" in source or "validationSchema:" in source
    assert has_validate, (
        f"ConfigModule in {module_path} has no 'validate:' or 'validationSchema:' option; "
        "env must be validated at startup"
    )


@pytest.mark.parametrize("module_path", CONFIG_MODULE_FILES, ids=lambda p: p.parts[-4])
def test_when_app_module_is_read_then_database_url_is_required_in_env_validation(
    module_path,
):
    """Criterion: the env validation schema requires DATABASE_URL.

    Assumption: the validation schema (Zod or Joi) declares DATABASE_URL as a required field.
    We check either the app.module.ts directly or expect a co-located env.validation.ts file.
    """
    source = read_text(module_path)

    # Check inline or look for an adjacent validation file
    validation_file = module_path.parent / "config" / "env.validation.ts"
    alt_validation_file = module_path.parent / "env.validation.ts"

    combined = source
    for candidate in (validation_file, alt_validation_file):
        if candidate.exists():
            combined += candidate.read_text(encoding="utf-8")

    assert "DATABASE_URL" in combined, (
        f"DATABASE_URL not referenced in env validation in {module_path} or its siblings"
    )


@pytest.mark.parametrize(
    "module_path",
    [
        PI / "templates-supabase-nestjs" / "api" / "src" / "app.module.ts",
    ],
    ids=["supabase"],
)
def test_when_supabase_app_module_is_read_then_supabase_secrets_are_required_in_env_validation(
    module_path,
):
    """Criterion: supabase variant env validation requires SUPABASE_* secrets.

    Assumption: at least SUPABASE_URL is named in the validation schema.
    """
    source = read_text(module_path)

    validation_file = module_path.parent / "config" / "env.validation.ts"
    alt_validation_file = module_path.parent / "env.validation.ts"

    combined = source
    for candidate in (validation_file, alt_validation_file):
        if candidate.exists():
            combined += candidate.read_text(encoding="utf-8")

    assert "SUPABASE_URL" in combined, (
        f"SUPABASE_URL not referenced in env validation in {module_path} or siblings"
    )


# ---------------------------------------------------------------------------
# Criterion 3: Response schemas whitelist fields (no secret-column leakage)
# ---------------------------------------------------------------------------


def test_when_response_schemas_are_collected_then_at_least_one_exists():
    """Guard: at least one *.dto.ts response DTO file must exist in the NestJS templates."""
    assert len(ALL_RESPONSE_SCHEMA_FILES) > 0, (
        "No *.dto.ts files found under templates-*-nestjs/api/src; "
        "response DTOs must exist for Zod whitelisting to be testable"
    )


@pytest.mark.parametrize(
    "schema_path", ALL_RESPONSE_SCHEMA_FILES, ids=lambda p: "/".join(p.parts[-4:])
)
def test_when_response_schema_file_is_read_then_it_uses_zod_object_not_passthrough(
    schema_path,
):
    """Criterion: response schemas use explicit field whitelisting (z.object with named keys).

    Assumption: Zod whitelisting means the schema is defined with `z.object({...})`.
    The absence of `.passthrough()` confirms unknown keys are stripped.
    We assert z.object is present and .passthrough() is absent.
    """
    source = read_text(schema_path)
    assert "z.object" in source, (
        f"Response schema {schema_path} does not use z.object; cannot guarantee field whitelisting"
    )
    assert ".passthrough()" not in source, (
        f"Response schema {schema_path} uses .passthrough(), which leaks unknown fields from Prisma rows"
    )


@pytest.mark.parametrize(
    "schema_path", ALL_RESPONSE_SCHEMA_FILES, ids=lambda p: "/".join(p.parts[-4:])
)
def test_when_response_schema_file_is_read_then_password_field_is_not_included(
    schema_path,
):
    """Criterion: response schemas do not expose a 'password' field.

    Assumption: if a schema contains `password:` as a named Zod field it would leak the
    password column. The criterion states Prisma rows must not leak secret columns.
    """
    source = read_text(schema_path)
    # Allow 'password' only as a comment or import name, not as a schema key
    schema_body_pattern = re.compile(r"z\.object\s*\(\s*\{([\s\S]*?)\}\s*\)", re.DOTALL)
    for match in schema_body_pattern.finditer(source):
        body = match.group(1)
        assert "password" not in body, (
            f"Response schema {schema_path} exposes 'password' inside z.object body"
        )


# ---------------------------------------------------------------------------
# Property: no response schema file uses .passthrough() (invariant over the set)
# ---------------------------------------------------------------------------


@given(
    st.sampled_from(ALL_RESPONSE_SCHEMA_FILES)
    if ALL_RESPONSE_SCHEMA_FILES
    else st.nothing()
)
def test_when_any_response_schema_is_read_then_passthrough_is_never_used(schema_path):
    """Property: the no-.passthrough() invariant holds for every response schema file."""
    source = read_text(schema_path)
    assert ".passthrough()" not in source, (
        f"{schema_path} uses .passthrough(), leaking Prisma columns through the serializer"
    )
