"""
Source-blind example tests for Issue #12: fix ChatJobStatus serialization 500 error.

Derived from acceptance criteria and requirements.md — no implementation source read.
Tests are in TDD Red phase: they fail until each criterion is genuinely satisfied.

Skipped criteria (oracle: NOT VERIFIABLE):
- Terminus health module (no concrete runtime/unit check inferable)
- e2e test scaffold / service unit spec (no concrete check inferable)
- BullMQ offload (optional, no concrete check inferable)
- All tests pass gate (boilerplate suite gate)
- SOLID code quality (subjective prose)

Hypothesis @given properties: none emitted.
All verifiable criteria reduce to structural assertions on template files at rest;
none imply a round-trip, idempotence, never-raises, or ordering invariant over an
unbounded Python-callable input domain.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PI = REPO_ROOT / "project_initializer"

NESTJS_BASE = PI / "templates-api-nestjs"
NESTJS_TOKEN = PI / "templates-token-nestjs"
NESTJS_SUPABASE = PI / "templates-supabase-nestjs"

_APP_MODULE = Path("api/src/app.module.ts")

# Paths to the chatbot DTO and job-service spec within the base template.
# Derived from criteria text: criteria mention ChatJobStatusSchema (a DTO), ChatJobStatusDto,
# and GET /chat/jobs/:id (a chatbot-module endpoint) — locating these under modules/chatbot/.
_CHAT_DTO = NESTJS_BASE / "api" / "src" / "modules" / "chatbot" / "dto" / "chat.dto.ts"
_CHAT_JOB_SPEC = (
    NESTJS_BASE / "api" / "src" / "modules" / "chatbot" / "chat-job.service.spec.ts"
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _read(path: Path) -> str:
    assert path.exists(), f"Expected template file not found: {path}"
    return path.read_text(encoding="utf-8")


def _read_overlay(template_dir: Path, rel: Path) -> str:
    return _read(template_dir / rel)


# ══════════════════════════════════════════════════════════════════════════════
# Global criterion [UNIT]:
# Auth guard registered as APP_GUARD in token and supabase overlays.
# ══════════════════════════════════════════════════════════════════════════════


def test_when_token_overlay_app_module_is_read_then_auth_guard_is_registered_as_app_guard():
    """AuthGuard must be provided as APP_GUARD so every route is protected by default;
    without it, token-auth routes are open to unauthenticated callers."""
    content = _read_overlay(NESTJS_TOKEN, _APP_MODULE)
    assert "APP_GUARD" in content, (
        "token overlay app.module.ts must declare APP_GUARD — "
        "without it routes are unprotected by default"
    )
    assert "AuthGuard" in content, (
        "token overlay app.module.ts must reference AuthGuard as the APP_GUARD useClass"
    )


def test_when_supabase_overlay_app_module_is_read_then_supabase_auth_guard_is_registered_as_app_guard():
    """SupabaseAuthGuard must be provided as APP_GUARD so every route is protected by
    default in the Supabase variant."""
    content = _read_overlay(NESTJS_SUPABASE, _APP_MODULE)
    assert "APP_GUARD" in content, (
        "supabase overlay app.module.ts must declare APP_GUARD"
    )
    assert "SupabaseAuthGuard" in content, (
        "supabase overlay app.module.ts must reference SupabaseAuthGuard as the APP_GUARD useClass"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Global criterion [UNIT]:
# ConfigModule validates env and fails fast on missing secrets.
# ══════════════════════════════════════════════════════════════════════════════


def test_when_base_app_module_is_read_then_config_module_receives_a_validate_function():
    """ConfigModule.forRoot must receive a validate: callback so that the process exits
    immediately when required env vars (DATABASE_URL, SUPABASE_*) are absent, rather
    than failing silently at the first DB/API call."""
    content = _read_overlay(NESTJS_BASE, _APP_MODULE)
    assert "ConfigModule" in content, "app.module.ts must import ConfigModule"
    assert "validate" in content, (
        "ConfigModule.forRoot must pass a validate function for fast-fail env validation"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Global criterion [UNIT]:
# Response schemas whitelist fields so Prisma rows cannot leak secret columns.
# ══════════════════════════════════════════════════════════════════════════════


def test_when_dto_files_are_scanned_then_no_dto_exposes_a_password_field():
    """All *.dto.ts files in the base NestJS template must not expose a 'password' field.
    The ZodSerializerInterceptor whitelists by the response schema, so any field declared
    in a response schema can be serialised to the client — password must not appear."""
    src_dir = NESTJS_BASE / "api" / "src"
    assert src_dir.exists(), f"Expected NestJS src dir not found: {src_dir}"
    dto_files = list(src_dir.rglob("*.dto.ts"))
    assert dto_files, (
        "No *.dto.ts files found under templates-api-nestjs/api/src/ — "
        "at minimum chat.dto.ts must exist"
    )
    for dto_file in dto_files:
        content = dto_file.read_text(encoding="utf-8")
        assert not re.search(r"\bpassword\b\s*:", content), (
            f"{dto_file.name} exposes a 'password' field — "
            "response schemas must whitelist fields to prevent Prisma row leakage"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Scope criterion [UNIT]:
# ChatJobStatusSchema result field accepts null so ZodSerializerInterceptor does
# not throw for waiting/active/delayed/failed states.
# ══════════════════════════════════════════════════════════════════════════════


def test_when_chat_dto_is_read_then_chat_job_status_schema_result_field_accepts_null():
    """ChatJobStatusSchema.result must be declared as nullish(), nullable(), or optional()
    (or a combination) so that the ZodSerializerInterceptor can serialise a status object
    with a missing/null result without throwing a 500.

    Acceptable patterns from the criterion text:
    - ChatResponseSchema.nullish()      → null | undefined
    - ChatResponseSchema.nullable()     → null
    - ChatResponseSchema.optional()     → undefined (when service omits the key)
    - ChatResponseSchema.nullable().optional()
    """
    content = _read(_CHAT_DTO)
    assert re.search(
        r"result\s*:.*\.(nullish|nullable|optional)\(",
        content,
    ), (
        "ChatJobStatusSchema must declare its result field as nullish(), nullable(), or optional() "
        "so the serializer does not throw when result is null for non-completed jobs. "
        "The criterion permits either schema-side nullish or service-side omission (undefined)."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Scope criterion [UNIT]:
# GET /chat/jobs/:id returns HTTP 200 for waiting, active, delayed, and failed states.
# Verified via the spec: the spec must exercise each state explicitly.
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("state", ["waiting", "active", "delayed", "failed"])
def test_when_chat_job_spec_is_read_then_non_completed_state_is_covered(state: str):
    """chat-job.service.spec.ts must include a test case covering the '{state}' state
    to confirm the endpoint returns HTTP 200 (not 500) when result is absent.

    Assumption: the spec file is co-located with the service at
    src/modules/chatbot/chat-job.service.spec.ts (NestJS convention).
    """
    content = _read(_CHAT_JOB_SPEC)
    assert state in content, (
        f"chat-job.service.spec.ts must contain a test case for the '{state}' state — "
        f"GET /chat/jobs/:id must return 200 (not 500) when job is in that state"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Scope criterion [UNIT]:
# GET /chat/jobs/:id still returns the { answer } object for a completed job.
# ══════════════════════════════════════════════════════════════════════════════


def test_when_chat_job_spec_is_read_then_completed_state_returns_answer_object():
    """The spec must assert that a completed job returns the { answer } payload, confirming
    the happy-path is not broken by the null-result fix.

    Both 'completed' state and 'answer' field must appear in the spec because:
    - 'completed' identifies the test case for the happy-path state
    - 'answer' confirms the expected response shape is asserted
    """
    content = _read(_CHAT_JOB_SPEC)
    assert "completed" in content, (
        "chat-job.service.spec.ts must include a test case for the 'completed' state"
    )
    assert "answer" in content, (
        "chat-job.service.spec.ts must assert the 'answer' field for a completed job — "
        "the happy-path shape must not be silently dropped by the null-result fix"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Scope criterion [UNIT]:
# A test exercises the actual serializer contract via .parse() with null/absent result,
# not just a plain controller-method unit test (which bypasses the interceptor).
# ══════════════════════════════════════════════════════════════════════════════


def test_when_chat_job_spec_is_read_then_schema_parse_is_exercised():
    """The spec must call .parse() on ChatJobStatusSchema or ChatJobStatusDto.schema
    to test the Zod serializer contract directly.

    A plain controller-method unit test returns a plain object and bypasses the
    ZodSerializerInterceptor, so only a .parse() call (or e2e/interceptor-level test)
    actually exercises the 500-causing code path. This criterion requires .parse() to appear.
    """
    content = _read(_CHAT_JOB_SPEC)
    assert re.search(r"\bparse\(", content), (
        "chat-job.service.spec.ts must call .parse() on ChatJobStatusSchema or "
        "ChatJobStatusDto.schema to exercise the ZodSerializerInterceptor contract — "
        "a plain controller-method unit test is insufficient per the criterion"
    )


def test_when_chat_job_spec_is_read_then_a_null_or_absent_result_is_parsed_without_throwing():
    """The spec must exercise .parse() with result: null or result: undefined (absent) and
    assert it does not throw, directly confirming the 500-regression is fixed.

    Assumption: the spec represents a non-completed status with an explicit null or
    undefined result value in the object passed to parse().
    """
    content = _read(_CHAT_JOB_SPEC)
    has_null_result_in_parse_context = bool(
        re.search(r"result\s*:\s*(null|undefined)", content)
        or '"result": null' in content
        or "'result': null" in content
    )
    assert has_null_result_in_parse_context, (
        "chat-job.service.spec.ts must include a parse() call with result: null or "
        "result: undefined to confirm the serializer does not throw for non-completed jobs"
    )
