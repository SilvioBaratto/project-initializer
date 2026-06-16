"""
Source-blind example tests for issue #14: NestJS BAML chatbot docs + template hardening.

Tests derived exclusively from the issue #14 acceptance criteria and
.code-generator/requirements.md. Criteria classified [NOT VERIFIABLE] by the oracle
(Terminus health, e2e scaffold, BullMQ offload, all-tests-pass, SOLID quality) are
intentionally skipped.

Verifiable criteria covered here:
  [UNIT-1] APP_GUARD registered in both the token and supabase overlays
  [UNIT-2] ConfigModule validates env and fails fast on missing secrets
  [UNIT-3] Response schemas whitelist fields (no secret column leaks)
  [UNIT-4] CLAUDE.md documents the BAML call flow (controller → service → worker)
  [UNIT-5] CLAUDE.md states baml_src/*.baml location and regeneration command
  [UNIT-6] CLAUDE.md notes TypeScript target with async default client mode
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

# Exact path required by the criterion text
CLAUDE_MD_PATH = NESTJS_BASE_API / ".claude" / "CLAUDE.md"


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


def test_when_token_app_module_is_read_then_app_guard_is_registered():
    """
    Criterion: the token overlay registers its auth guard as APP_GUARD so routes
    are protected by default; missing this is the biggest security risk.
    Assumption: the overlay provides an app.module.ts under templates-token-nestjs/api/.
    """
    ts_files = _ts_files(NESTJS_TOKEN_API)
    assert ts_files, "No .ts files found in templates-token-nestjs/api/"

    app_modules = [f for f in ts_files if f.name.lower() in ("app.module.ts",)]
    assert app_modules, (
        "No app.module.ts found in templates-token-nestjs/api/; "
        "the token overlay must provide an app module that registers APP_GUARD"
    )

    content = _read(app_modules[0])
    assert "APP_GUARD" in content, (
        f"APP_GUARD not registered in {app_modules[0]}; "
        "the token auth guard must be a global APP_GUARD provider so all routes are protected"
    )


# ── [UNIT-1] APP_GUARD: supabase overlay ─────────────────────────────────────


def test_when_supabase_app_module_is_read_then_app_guard_is_registered():
    """
    Criterion: the supabase overlay registers its auth guard as APP_GUARD so routes
    are protected by default.
    Assumption: the overlay provides an app.module.ts under templates-supabase-nestjs/api/.
    """
    ts_files = _ts_files(NESTJS_SUPABASE_API)
    assert ts_files, "No .ts files found in templates-supabase-nestjs/api/"

    app_modules = [f for f in ts_files if f.name.lower() in ("app.module.ts",)]
    assert app_modules, (
        "No app.module.ts found in templates-supabase-nestjs/api/; "
        "the supabase overlay must provide an app module that registers APP_GUARD"
    )

    content = _read(app_modules[0])
    assert "APP_GUARD" in content, (
        f"APP_GUARD not registered in {app_modules[0]}; "
        "the supabase auth guard must be a global APP_GUARD provider so all routes are protected"
    )


# ── [UNIT-2] ConfigModule: validate function present ──────────────────────────


def test_when_config_module_setup_is_read_then_validate_option_is_present():
    """
    Criterion: ConfigModule validates env and fails fast on missing secrets
    (DATABASE_URL, SUPABASE_*). A `validate` option must be passed to
    ConfigModule.forRoot so startup aborts when required vars are absent.
    Assumption: the validate option appears in a .ts file in the base or any
    auth overlay.
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
    sensitive columns (e.g. password) through the ZodSerializerInterceptor.
    Assumption: at least one response schema or DTO file exists for the User
    entity; it must not expose a `password` field.
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
    return [
        f
        for f in _ts_files(NESTJS_BASE_API, NESTJS_TOKEN_API, NESTJS_SUPABASE_API)
        if re.search(r"schema|dto|response", f.name, re.IGNORECASE)
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


# ── [UNIT-4] CLAUDE.md: BAML call flow documentation ─────────────────────────


def test_when_claude_md_is_read_then_baml_call_flow_is_documented():
    """
    Criterion: templates-api-nestjs/api/.claude/CLAUDE.md documents the BAML call
    flow: controller → ChatbotService.chat / streamChat and the ChatProcessor worker,
    each dynamically importing baml_client and calling b.Chat / b.stream.StreamChat.
    """
    content = _read(CLAUDE_MD_PATH)

    assert "ChatbotService" in content, (
        "CLAUDE.md does not mention ChatbotService; "
        "the doc must document controller → ChatbotService.chat / streamChat"
    )
    assert re.search(r"\bstreamChat\b", content), (
        "CLAUDE.md does not mention streamChat; "
        "the call flow must document both chat and streamChat methods"
    )
    assert "ChatProcessor" in content, (
        "CLAUDE.md does not mention ChatProcessor; "
        "the BAML call flow must include the ChatProcessor worker"
    )
    assert "baml_client" in content, (
        "CLAUDE.md does not mention baml_client; "
        "the doc must state that each handler dynamically imports baml_client"
    )
    assert re.search(r"b\.Chat", content), (
        "CLAUDE.md does not reference b.Chat; "
        "the call flow must document the b.Chat entry point"
    )
    assert re.search(r"b\.stream\.StreamChat", content), (
        "CLAUDE.md does not reference b.stream.StreamChat; "
        "the call flow must document the streaming b.stream.StreamChat entry point"
    )


# ── [UNIT-5] CLAUDE.md: baml_src location + regeneration command ─────────────


def test_when_claude_md_is_read_then_baml_src_location_and_regen_command_are_stated():
    """
    Criterion: the doc states where LLM functions are defined (baml_src/*.baml),
    how to regenerate the client (npx baml-cli generate), and that baml_client/
    is generated and must not be hand-edited.
    """
    content = _read(CLAUDE_MD_PATH)

    assert "baml_src" in content, (
        "CLAUDE.md does not mention baml_src; "
        "the doc must state that LLM functions are defined in baml_src/*.baml"
    )
    assert ".baml" in content, (
        "CLAUDE.md does not reference .baml files; "
        "the doc must indicate LLM functions live in baml_src/*.baml"
    )
    assert "npx baml-cli generate" in content, (
        "CLAUDE.md does not include 'npx baml-cli generate'; "
        "the doc must state the regeneration command"
    )
    assert re.search(
        r"must not.*hand.edit|do not.*hand.edit|not.*edit.*by hand|generated.*must not|hand.edited",
        content,
        re.IGNORECASE,
    ), (
        "CLAUDE.md does not warn that baml_client/ must not be hand-edited; "
        "the doc must note that baml_client/ is generated output"
    )


# ── [UNIT-6] CLAUDE.md: TypeScript target + async default client mode ─────────


def test_when_claude_md_is_read_then_typescript_target_and_async_client_mode_are_noted():
    """
    Criterion: the doc notes the generator targets TypeScript with async default
    client mode (baml_src/generators.baml).
    """
    content = _read(CLAUDE_MD_PATH)

    assert "generators.baml" in content, (
        "CLAUDE.md does not mention generators.baml; "
        "the doc must reference baml_src/generators.baml"
    )
    assert re.search(r"TypeScript|typescript", content), (
        "CLAUDE.md does not mention the TypeScript target; "
        "the doc must note that the BAML generator targets TypeScript"
    )
    assert re.search(
        r"async.*default.*client|default.*client.*async|async.*client.*mode",
        content,
        re.IGNORECASE,
    ), (
        "CLAUDE.md does not mention async default client mode; "
        "the doc must note that generators.baml configures async default client mode"
    )
