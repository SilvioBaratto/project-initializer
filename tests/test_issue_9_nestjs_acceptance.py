"""
Source-blind acceptance tests for issue #9:
feat: harden chat job failure handling and retry policy

Derived solely from the acceptance criteria text. Reads NestJS template files
at test-run time and asserts the observable contract demanded by each criterion.
All tests are in the Red phase — they fail before the implementation lands.
"""

import re
from pathlib import Path

# ── Template file paths (not opened by the test designer) ─────────────────

_BASE = Path("project_initializer/templates-api-nestjs/api/src")
_TOKEN = Path("project_initializer/templates-token-nestjs/api/src")
_SUPABASE = Path("project_initializer/templates-supabase-nestjs/api/src")

_BASE_APP_MODULE = _BASE / "app.module.ts"
_TOKEN_APP_MODULE = _TOKEN / "app.module.ts"
_SUPABASE_APP_MODULE = _SUPABASE / "app.module.ts"
_CHATBOT_MODULE = _BASE / "modules/chatbot/chatbot.module.ts"
_CHAT_PROCESSOR = _BASE / "modules/chatbot/chat.processor.ts"
_CHAT_PROCESSOR_SPEC = _BASE / "modules/chatbot/chat.processor.spec.ts"
_CHAT_DTO = _BASE / "modules/chatbot/dto/chat.dto.ts"


# ── Global criterion: Auth guard registered as APP_GUARD in token overlay ──


def test_when_token_app_module_is_inspected_auth_guard_is_registered_as_app_guard():
    """
    Criterion: The auth guard is confirmed registered as APP_GUARD in the
    token overlay so routes are protected by default.
    """
    content = _TOKEN_APP_MODULE.read_text(encoding="utf-8")
    assert re.search(r"provide\s*:\s*APP_GUARD", content), (
        "token overlay app.module.ts must declare a provider with provide: APP_GUARD"
    )
    assert re.search(r"useClass\s*:\s*AuthGuard", content), (
        "token overlay APP_GUARD provider must use AuthGuard"
    )


def test_when_supabase_app_module_is_inspected_auth_guard_is_registered_as_app_guard():
    """
    Criterion: The auth guard is confirmed registered as APP_GUARD in the
    supabase overlay so routes are protected by default.
    """
    content = _SUPABASE_APP_MODULE.read_text(encoding="utf-8")
    assert re.search(r"provide\s*:\s*APP_GUARD", content), (
        "supabase overlay app.module.ts must declare a provider with provide: APP_GUARD"
    )
    assert re.search(r"useClass\s*:\s*SupabaseAuthGuard", content), (
        "supabase overlay APP_GUARD provider must use SupabaseAuthGuard"
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


def test_when_chat_dto_is_inspected_response_schema_does_not_include_sensitive_field_names():
    """
    Criterion: Response schemas whitelist fields so Prisma rows cannot leak
    secret columns (e.g. password / secrets) through the serializer.
    Chat response DTOs must not declare password or secret fields.
    """
    content = _CHAT_DTO.read_text(encoding="utf-8")
    assert not re.search(r"\bpassword\b", content, re.IGNORECASE), (
        "chat response DTO must not expose a 'password' field"
    )
    assert not re.search(r"\bpasswordHash\b|\bsecretKey\b", content, re.IGNORECASE), (
        "chat response DTO must not expose password-hash or secret-key fields"
    )


# ── Scope criterion: Processor rethrows on BAML error ─────────────────────


def test_when_chat_processor_encounters_baml_error_it_does_not_return_fallback_answer():
    """
    Criterion: On a BAML/LLM error the processor signals failure (rethrows)
    so BullMQ records the job as 'failed' after retries are exhausted.

    A processor that catches errors and returns { answer: '…error…' } prevents
    BullMQ from ever recording the job as failed. That fallback must be removed.
    """
    content = _CHAT_PROCESSOR.read_text(encoding="utf-8")
    assert "Sorry, I encountered an error processing your request." not in content, (
        "processor must not return a fallback answer string that masks BAML failures"
    )


def test_when_chat_processor_errors_no_catch_block_silently_returns_fallback():
    """
    Criterion: Processor must rethrow BAML errors so BullMQ sees the failure.
    A catch block that returns { answer: '...' } silently completes the job.
    """
    content = _CHAT_PROCESSOR.read_text(encoding="utf-8")
    swallow_pattern = re.compile(
        r"catch\s*\([^)]*\)\s*\{[^}]*return\s*\{[^}]*answer\s*:",
        re.DOTALL,
    )
    assert not swallow_pattern.search(content), (
        "processor must not catch BAML errors and silently return { answer: '...' }"
    )


# ── Scope criterion: defaultJobOptions with attempts > 1 ──────────────────


def test_when_chatbot_module_is_inspected_chat_queue_registration_includes_default_job_options():
    """
    Criterion: The chat queue defines defaultJobOptions.
    """
    content = _CHATBOT_MODULE.read_text(encoding="utf-8")
    assert "defaultJobOptions" in content, (
        "chatbot.module.ts BullModule.registerQueue must include defaultJobOptions"
    )


def test_when_chatbot_module_is_inspected_default_job_options_has_attempts_greater_than_one():
    """
    Criterion: defaultJobOptions has attempts (>1) to enable retries.
    """
    content = _CHATBOT_MODULE.read_text(encoding="utf-8")
    match = re.search(r"attempts\s*:\s*(\d+)", content)
    assert match is not None, (
        "defaultJobOptions must include a numeric 'attempts' value"
    )
    assert int(match.group(1)) > 1, (
        f"attempts must be > 1 to retry transient failures, got {match.group(1)}"
    )


# ── Scope criterion: defaultJobOptions with exponential backoff ────────────


def test_when_chatbot_module_is_inspected_default_job_options_configures_exponential_backoff():
    """
    Criterion: defaultJobOptions has exponential backoff.
    """
    content = _CHATBOT_MODULE.read_text(encoding="utf-8")
    assert re.search(r"backoff\s*:", content), (
        "defaultJobOptions must include a backoff configuration"
    )
    assert re.search(r"exponential", content, re.IGNORECASE), (
        "backoff type must be set to 'exponential'"
    )


# ── Scope criterion: defaultJobOptions with removeOnComplete bounds ─────────


def test_when_chatbot_module_is_inspected_default_job_options_has_remove_on_complete():
    """
    Criterion: defaultJobOptions has removeOnComplete bounds to cap Redis growth.
    """
    content = _CHATBOT_MODULE.read_text(encoding="utf-8")
    assert re.search(r"removeOnComplete\s*:", content), (
        "defaultJobOptions must include removeOnComplete to bound Redis memory"
    )


def test_when_chatbot_module_remove_on_complete_is_a_bounded_value_not_plain_true():
    """
    Criterion: removeOnComplete must be a bounded value (count or age), not
    plain boolean true.

    Assumption: plain `true` removes jobs immediately upon completion, which
    breaks the GET /chat/jobs/:id poll-for-result flow — callers would receive
    NotFoundException instead of the answer. The criterion says 'bounds to cap
    Redis growth', which requires a count or age object, not immediate removal.
    """
    content = _CHATBOT_MODULE.read_text(encoding="utf-8")
    assert not re.search(r"removeOnComplete\s*:\s*true\b", content), (
        "removeOnComplete must not be plain 'true'; use { count: N } or { age: N } "
        "so completed jobs remain retrievable within a bounded retention window"
    )


# ── Scope criterion: defaultJobOptions with removeOnFail bounds ────────────


def test_when_chatbot_module_is_inspected_default_job_options_has_remove_on_fail():
    """
    Criterion: defaultJobOptions has removeOnFail bounds to cap Redis growth.
    """
    content = _CHATBOT_MODULE.read_text(encoding="utf-8")
    assert re.search(r"removeOnFail\s*:", content), (
        "defaultJobOptions must include removeOnFail to bound Redis memory"
    )


# ── Scope criterion: @OnWorkerEvent('failed') handler ─────────────────────


def test_when_chat_processor_is_inspected_it_declares_an_on_worker_event_failed_handler():
    """
    Criterion: A @OnWorkerEvent('failed') (or equivalent) handler is present
    in the processor.
    """
    content = _CHAT_PROCESSOR.read_text(encoding="utf-8")
    assert re.search(r"OnWorkerEvent\s*\(\s*['\"]failed['\"]\s*\)", content), (
        "chat.processor.ts must declare a @OnWorkerEvent('failed') handler"
    )


def test_when_chat_processor_failed_handler_fires_it_logs_via_nest_logger():
    """
    Criterion: The @OnWorkerEvent('failed') handler logs failures via the
    Nest Logger.
    """
    content = _CHAT_PROCESSOR.read_text(encoding="utf-8")
    assert "Logger" in content, "chat.processor.ts must import NestJS Logger"
    assert re.search(r"this\.logger\.(error|warn|log)\s*\(", content), (
        "the failed handler must call this.logger.error / warn / log"
    )


# ── Scope criterion: Spec updated — no silent fallback assertion ───────────


def test_when_chat_processor_spec_is_inspected_it_does_not_assert_the_old_fallback_message():
    """
    Criterion: chat.processor.spec.ts no longer asserts the silent fallback.
    The old assertion matching 'Sorry, I encountered an error…' must be removed.
    """
    content = _CHAT_PROCESSOR_SPEC.read_text(encoding="utf-8")
    assert "Sorry, I encountered an error processing your request." not in content, (
        "chat.processor.spec.ts must not assert the fallback error string; "
        "it should assert that process() rejects/throws instead"
    )


def test_when_chat_processor_spec_is_inspected_it_asserts_error_propagation_on_baml_failure():
    """
    Criterion: chat.processor.spec.ts asserts failure-propagation + retry
    semantics — the spec must verify process() rejects on BAML error.
    """
    content = _CHAT_PROCESSOR_SPEC.read_text(encoding="utf-8")
    assert re.search(r"\brejects\b|\btoThrow\b", content), (
        "spec must assert that process() rejects or throws on BAML error"
    )


def test_when_chat_processor_spec_is_inspected_it_covers_the_failed_event_logger():
    """
    Criterion: chat.processor.spec.ts adds a case covering the failed-event
    logger (@OnWorkerEvent('failed') handler behaviour).
    """
    content = _CHAT_PROCESSOR_SPEC.read_text(encoding="utf-8")
    assert re.search(
        r"['\"]failed['\"]|onFailed|OnWorkerEvent|failed.*[Ll]ogger|[Ll]ogger.*failed",
        content,
        re.IGNORECASE,
    ), (
        "spec must include a test case that exercises the @OnWorkerEvent('failed') "
        "handler and asserts that Logger is called"
    )
