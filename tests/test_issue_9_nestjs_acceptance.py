"""
Source-blind acceptance tests for issue #9: the global criteria of the NestJS template
(global auth guard, env validation, response whitelist).

Derived solely from the acceptance criteria text. Reads NestJS template files
at test-run time and asserts the observable contract demanded by each criterion.
"""

import re
from pathlib import Path

# ── Template file paths (not opened by the test designer) ─────────────────

_BASE = Path("project_initializer/templates-api-nestjs/api/src")
_TOKEN = Path("project_initializer/templates-token-nestjs/api/src")
_SUPABASE = Path("project_initializer/templates-supabase-nestjs/api/src")

_BASE_APP_MODULE = _BASE / "app.module.ts"
# The root module is shared; each overlay's `app.auth.ts` registers the global guard.
_TOKEN_APP_AUTH = _TOKEN / "app.auth.ts"
_SUPABASE_APP_AUTH = _SUPABASE / "app.auth.ts"
_ITEM_DTO = _BASE / "modules/items/dto/item.dto.ts"


# ── Global criterion: Auth guard registered as APP_GUARD in token overlay ──


def test_when_token_app_auth_is_inspected_auth_guard_is_registered_as_app_guard():
    """
    Criterion: The auth guard is confirmed registered as APP_GUARD in the
    token overlay so routes are protected by default.

    Validates project_initializer/templates-token-nestjs/api/src/app.auth.ts.
    """
    content = _TOKEN_APP_AUTH.read_text(encoding="utf-8")
    assert re.search(r"provide\s*:\s*APP_GUARD", content), (
        "token overlay app.auth.ts must declare a provider with provide: APP_GUARD"
    )
    assert re.search(r"useClass\s*:\s*AccessTokenGuard", content), (
        "token overlay APP_GUARD provider must use AccessTokenGuard"
    )


def test_when_supabase_app_auth_is_inspected_auth_guard_is_registered_as_app_guard():
    """
    Criterion: The auth guard is confirmed registered as APP_GUARD in the
    supabase overlay so routes are protected by default.

    Validates project_initializer/templates-supabase-nestjs/api/src/app.auth.ts.
    """
    content = _SUPABASE_APP_AUTH.read_text(encoding="utf-8")
    assert re.search(r"provide\s*:\s*APP_GUARD", content), (
        "supabase overlay app.auth.ts must declare a provider with provide: APP_GUARD"
    )
    assert re.search(r"useClass\s*:\s*AccessTokenGuard", content), (
        "supabase overlay APP_GUARD provider must use AccessTokenGuard"
    )


# ── Global criterion: ConfigModule validates env ───────────────────────────


def test_when_base_app_module_is_inspected_config_module_wires_a_validate_function():
    """
    Criterion: ConfigModule validates env and fails fast on missing secrets
    (e.g. DATABASE_URL). ConfigModule.forRoot must include a validate option.
    """
    content = _BASE_APP_MODULE.read_text(encoding="utf-8")
    assert re.search(r"ConfigModule\.forRoot\s*\(", content), (
        "app.module.ts must call ConfigModule.forRoot"
    )
    assert re.search(r"validate\s*:", content), (
        "ConfigModule.forRoot must wire a validate: <fn> option for env validation"
    )


# ── Global criterion: Response schemas whitelist fields ────────────────────


def test_when_item_dto_is_inspected_response_schema_does_not_include_sensitive_field_names():
    """
    Criterion: Response schemas whitelist fields so Prisma rows cannot leak
    secret columns (e.g. password / secrets) through the serializer.
    Item response DTOs must not declare password or secret fields.

    Validates project_initializer/templates-api-nestjs/api/src/modules/items/dto/item.dto.ts.
    """
    content = _ITEM_DTO.read_text(encoding="utf-8")
    assert not re.search(r"\bpassword\b", content, re.IGNORECASE), (
        "item response DTO must not expose a 'password' field"
    )
    assert not re.search(r"\bpasswordHash\b|\bsecretKey\b", content, re.IGNORECASE), (
        "item response DTO must not expose password-hash or secret-key fields"
    )
