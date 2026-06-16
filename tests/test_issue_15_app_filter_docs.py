"""
Issue #15 — filter-DI APP_FILTER provider pattern documentation.

Tests are derived solely from acceptance criteria (source-blind, Red phase).
No implementation source has been read to author these tests.
"""

import re
from pathlib import Path

TEMPLATES = Path(__file__).parent.parent / "project_initializer"

TOKEN_APP_MODULE = (
    TEMPLATES / "templates-token-nestjs" / "api" / "src" / "app.module.ts"
)
SUPABASE_APP_MODULE = (
    TEMPLATES / "templates-supabase-nestjs" / "api" / "src" / "app.module.ts"
)
NESTJS_BASE_APP_MODULE = (
    TEMPLATES / "templates-api-nestjs" / "api" / "src" / "app.module.ts"
)
NESTJS_ENV_VALIDATION = (
    TEMPLATES / "templates-api-nestjs" / "api" / "src" / "config" / "env.validation.ts"
)
FILTER_DI_DOC = TEMPLATES / "templates-api-nestjs" / "api" / ".claude" / "CLAUDE.md"

# Candidate paths for a response schema that proves field whitelisting (Zod).
# The template's proof lives in the test module's item DTO; user/entity modules
# may also have their own response schemas.
_RESPONSE_SCHEMA_CANDIDATES = [
    # Primary: serialization-proof schema in the test module
    TEMPLATES
    / "templates-api-nestjs"
    / "api"
    / "src"
    / "modules"
    / "test"
    / "dto"
    / "item.dto.ts",
    # Secondary: user-specific response schemas (added by auth overlays or future issues)
    TEMPLATES
    / "templates-api-nestjs"
    / "api"
    / "src"
    / "modules"
    / "users"
    / "dto"
    / "user-response.schema.ts",
    TEMPLATES
    / "templates-api-nestjs"
    / "api"
    / "src"
    / "modules"
    / "users"
    / "dto"
    / "user.schema.ts",
]


# ── APP_GUARD in token overlay ───────────────────────────────────────────────


def test_when_token_overlay_app_module_is_read_then_app_guard_is_imported():
    """Token overlay app module must import the APP_GUARD injection token."""
    content = TOKEN_APP_MODULE.read_text(encoding="utf-8")
    assert "APP_GUARD" in content


def test_when_token_overlay_app_module_is_read_then_auth_guard_is_wired_as_app_guard():
    """
    Token overlay app module must register AuthGuard as the global APP_GUARD provider
    so every route is protected by default without an explicit guard decorator.
    """
    content = TOKEN_APP_MODULE.read_text(encoding="utf-8")
    # Both tokens must co-appear; the provider pattern is
    # { provide: APP_GUARD, useClass: AuthGuard }
    assert "APP_GUARD" in content and "AuthGuard" in content


# ── APP_GUARD in supabase overlay ────────────────────────────────────────────


def test_when_supabase_overlay_app_module_is_read_then_app_guard_is_imported():
    """Supabase overlay app module must import the APP_GUARD injection token."""
    content = SUPABASE_APP_MODULE.read_text(encoding="utf-8")
    assert "APP_GUARD" in content


def test_when_supabase_overlay_app_module_is_read_then_supabase_guard_is_wired_as_app_guard():
    """
    Supabase overlay app module must register SupabaseAuthGuard as the global APP_GUARD
    provider so every route is protected by default without an explicit guard decorator.
    """
    content = SUPABASE_APP_MODULE.read_text(encoding="utf-8")
    assert "APP_GUARD" in content and "SupabaseAuthGuard" in content


# ── ConfigModule env validation ──────────────────────────────────────────────


def test_when_nestjs_base_app_module_is_read_then_config_module_has_validate_option():
    """
    ConfigModule.forRoot in the base NestJS app module must wire a validate function
    so the process exits immediately when required environment variables are missing.
    """
    content = NESTJS_BASE_APP_MODULE.read_text(encoding="utf-8")
    # Either the inline validate: key or a validationSchema: key (Joi) must be present
    assert "validate:" in content or "validationSchema:" in content


def test_when_env_validation_module_is_read_then_database_url_is_required():
    """
    The env validation schema must declare DATABASE_URL as a required field so a
    missing database secret causes validate() to throw before the app accepts traffic.

    Assumption: env validation lives in src/config/env.validation.ts (the NestJS
    ConfigModule convention); app.module.ts imports and wires it via validate:.
    """
    content = NESTJS_ENV_VALIDATION.read_text(encoding="utf-8")
    assert "DATABASE_URL" in content


# ── Response schemas whitelist fields ────────────────────────────────────────


def test_when_response_schema_exists_then_password_field_is_absent():
    """
    A response Zod schema must not expose a password field.
    Whitelisting via an explicit z.object({...}) ensures Prisma rows cannot leak the
    password column through the ZodSerializerInterceptor.

    The template ships ItemResponseSchema in test/dto/item.dto.ts as the canonical
    proof (verified by serialization.spec.ts). Auth overlays may add user schemas.
    """
    schema_file = next((p for p in _RESPONSE_SCHEMA_CANDIDATES if p.exists()), None)
    assert schema_file is not None, (
        "No response schema file found. Expected one of:\n"
        + "\n".join(f"  {p}" for p in _RESPONSE_SCHEMA_CANDIDATES)
    )
    content = schema_file.read_text(encoding="utf-8")
    # The response schema must not list a 'password' key — its presence would allow
    # the secret column to be serialised in API responses.
    assert "password" not in content.lower()


# ── CLAUDE.md: APP_FILTER pattern documented ─────────────────────────────────


def test_when_filter_di_doc_exists_then_app_filter_token_is_mentioned():
    """CLAUDE.md must mention APP_FILTER so a reader knows the provider pattern by name."""
    content = FILTER_DI_DOC.read_text(encoding="utf-8")
    assert "APP_FILTER" in content


def test_when_filter_di_doc_exists_then_use_class_pattern_is_documented():
    """
    CLAUDE.md must document the { provide: APP_FILTER, useClass: ... } provider shape
    so contributors know how to register a filter that requires dependency injection.
    """
    content = FILTER_DI_DOC.read_text(encoding="utf-8")
    assert "useClass" in content


def test_when_filter_di_doc_exists_then_new_instantiation_in_main_is_addressed():
    """
    CLAUDE.md must reference main.ts when explaining the APP_FILTER pattern, so readers
    understand the contrast: useGlobalFilters(new Filter()) in main.ts cannot inject deps.
    """
    content = FILTER_DI_DOC.read_text(encoding="utf-8")
    assert "main.ts" in content


# ── CLAUDE.md: current filters described as dependency-free ─────────────────


def test_when_filter_di_doc_exists_then_use_global_filters_is_mentioned():
    """
    CLAUDE.md must reference useGlobalFilters() to describe how current filters are
    registered, confirming the reader that the existing setup is correct as-is.
    """
    content = FILTER_DI_DOC.read_text(encoding="utf-8")
    assert "useGlobalFilters" in content


def test_when_filter_di_doc_exists_then_doc_states_no_change_required_for_current_filters():
    """
    CLAUDE.md must state that the current dependency-free filters need no change today,
    so contributors do not migrate them to APP_FILTER without a real dependency need.
    """
    content = FILTER_DI_DOC.read_text(encoding="utf-8")
    lower = content.lower()
    assert (
        "no change" in lower
        or "not required" in lower
        or "no action" in lower
        or "fine" in lower
        or "as-is" in lower
        or "as is" in lower
    )


# ── CLAUDE.md: APP_FILTER code snippet and /exception-filters citation (T2) ──


def test_when_filter_di_doc_exists_then_app_filter_snippet_is_in_a_code_block():
    """
    CLAUDE.md must include a fenced code block containing an APP_FILTER provider
    example so readers can copy-paste the pattern without guessing the syntax.
    """
    content = FILTER_DI_DOC.read_text(encoding="utf-8")
    code_blocks = re.findall(r"```[\s\S]*?```", content)
    assert any("APP_FILTER" in block for block in code_blocks), (
        "CLAUDE.md must contain a fenced code block (``` ... ```) with an APP_FILTER "
        "provider example, e.g. { provide: APP_FILTER, useClass: MyFilter }"
    )


def test_when_filter_di_doc_exists_then_exception_filters_docs_page_is_cited():
    """
    CLAUDE.md must cite the NestJS exception-filters documentation page
    (/exception-filters) so readers can follow up on the official source.
    """
    content = FILTER_DI_DOC.read_text(encoding="utf-8")
    assert "/exception-filters" in content
