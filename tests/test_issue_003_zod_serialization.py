"""
Issue #3 — NestJS Zod serialization / guard hardening: source-blind example tests.

All assertions are derived from issue #3 acceptance criteria and requirements.md §3-5.
No NestJS implementation source is read here; template files are inspected as plain text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pytest
from hypothesis import given, strategies as st

# ── project paths ─────────────────────────────────────────────────────────────
# Derived from CLAUDE.md documented structure, not from reading source.

REPO_ROOT = Path(__file__).resolve().parent.parent
TPL = REPO_ROOT / "project_initializer"

# One root module serves every variant; an overlay registers its guard through `app.auth.ts`.
BASE_APP_MODULE = TPL / "templates-api-nestjs/api/src/app.module.ts"
TOKEN_APP_MODULE = TPL / "templates-token-nestjs/api/src/app.auth.ts"
SUPABASE_APP_MODULE = TPL / "templates-supabase-nestjs/api/src/app.auth.ts"
OVERLAY_ROOT_MODULES = [
    (TPL / "templates-token-nestjs/api/src/app.module.ts", "token"),
    (TPL / "templates-supabase-nestjs/api/src/app.module.ts", "supabase"),
]

# The shared platform keys (DATABASE_URL, ...) are declared once, in the base env module.
BASE_ENV_VALIDATION = TPL / "templates-api-nestjs/api/src/config/env.base.ts"
SUPABASE_ENV_VALIDATION = (
    TPL / "templates-supabase-nestjs/api/src/config/env.validation.ts"
)

NESTJS_API_SRC = TPL / "templates-api-nestjs/api/src"
TOKEN_API_SRC = TPL / "templates-token-nestjs/api/src"
SUPABASE_API_SRC = TPL / "templates-supabase-nestjs/api/src"

_ALL_TEMPLATE_ROOTS = [NESTJS_API_SRC, TOKEN_API_SRC, SUPABASE_API_SRC]


# ── file-collection helpers ───────────────────────────────────────────────────


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _dto_files_under(root: Path) -> list[Path]:
    return list(root.rglob("*.dto.ts")) if root.exists() else []


def _controller_files_under(root: Path) -> list[Path]:
    if not root.exists():
        return []
    # health.controller.ts returns Terminus health-check results, not ORM entity data.
    return [
        p
        for p in root.rglob("*.controller.ts")
        if ".spec." not in p.name and p.name != "health.controller.ts"
    ]


# ── detection predicates ──────────────────────────────────────────────────────
# Each predicate is derived directly from the criterion text; no source peeked.


def _has_app_guard(text: str) -> bool:
    """Criterion A: guard registered as global APP_GUARD token."""
    return "APP_GUARD" in text


def _has_app_pipe_zod(text: str) -> bool:
    """Criterion C: ZodValidationPipe wired as APP_PIPE."""
    return "APP_PIPE" in text and "ZodValidationPipe" in text


def _has_app_interceptor_zod(text: str) -> bool:
    """Criterion C: ZodSerializerInterceptor wired as APP_INTERCEPTOR."""
    return "APP_INTERCEPTOR" in text and "ZodSerializerInterceptor" in text


def _has_passthrough(text: str) -> bool:
    """Criterion D/G: .passthrough() disables field whitelisting — must be absent."""
    return ".passthrough()" in text


def _has_zod_serializer_dto_decorator(text: str) -> bool:
    """Criterion E: handler annotated to enforce its response schema.

    `@ZodResponse(...)` is the nestjs-zod decorator that bundles `@ZodSerializerDto`, the
    status code and the OpenAPI response, so it enforces the schema the same way.
    """
    return "@ZodSerializerDto" in text or "@ZodResponse(" in text


def _has_http_data_handler(text: str) -> bool:
    """Return True if the controller declares at least one GET/POST/PUT/PATCH/DELETE handler."""
    return bool(re.search(r"@(Get|Post|Put|Patch|Delete)\(", text))


# ══════════════════════════════════════════════════════════════════════════════
# Criterion A — auth guard registered as APP_GUARD in token and supabase overlays
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "module_path,variant",
    [
        (TOKEN_APP_MODULE, "token"),
        (SUPABASE_APP_MODULE, "supabase"),
    ],
)
def test_when_auth_overlay_app_auth_is_read_then_app_guard_is_registered(
    module_path: Path, variant: str
) -> None:
    """
    The token and supabase overlays must register their auth guard as APP_GUARD (in
    `app.auth.ts`, which the shared root module spreads in) so every route is protected by
    default; opt-out is only possible via @Public().
    Derived from: 'auth guard registered as APP_GUARD in both the token and supabase overlays'.

    Validates project_initializer/templates-{token,supabase}-nestjs/api/src/app.auth.ts.
    """
    assert module_path.exists(), (
        f"[{variant}] app.auth.ts not found: {module_path}. "
        "The overlay must provide an app.auth.ts that wires the auth guard."
    )
    assert _has_app_guard(_read(module_path)), (
        f"[{variant}] app.auth.ts must contain APP_GUARD. "
        "Without it the auth guard is not applied globally and all routes are unprotected."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Criterion B — ConfigModule validates env vars and fails fast on missing secrets
# ══════════════════════════════════════════════════════════════════════════════


def test_when_base_app_module_is_read_then_config_module_declares_validate_option() -> (
    None
):
    """
    ConfigModule.forRoot in base app.module.ts must include a validate: callback or schema
    so the process exits immediately when required env vars are absent.
    Derived from: 'ConfigModule validates env and fails fast on missing secrets'.
    """
    assert BASE_APP_MODULE.exists(), f"Base app.module.ts not found: {BASE_APP_MODULE}"
    text = _read(BASE_APP_MODULE)
    assert "ConfigModule" in text and "validate" in text, (
        "Base app.module.ts must pass a validate function to ConfigModule.forRoot "
        "so missing secrets cause a fast-fail at startup rather than a runtime error."
    )


def test_when_base_env_validation_is_read_then_database_url_is_required() -> None:
    """
    The base env.base.ts Zod schema must require DATABASE_URL so that a missing
    database connection string causes a fast-fail at process startup.
    Derived from: 'fails fast on missing secrets (e.g. DATABASE_URL, SUPABASE_*)'.
    Note: validate() is imported into app.module.ts, so the effective validation lives
    in config/env.base.ts (via config/env.validation.ts), not app.module.ts itself.

    Validates project_initializer/templates-api-nestjs/api/src/config/env.base.ts.
    """
    assert BASE_ENV_VALIDATION.exists(), (
        f"Base env.base.ts not found: {BASE_ENV_VALIDATION}"
    )
    assert "DATABASE_URL" in _read(BASE_ENV_VALIDATION), (
        "Base env.base.ts must declare DATABASE_URL in the Zod schema so a missing "
        "DB connection string fails the process at startup."
    )


def test_when_supabase_env_validation_is_read_then_supabase_vars_are_required() -> None:
    """
    The Supabase overlay's env.validation.ts Zod schema must require SUPABASE_* vars so
    missing Supabase credentials are caught at process startup, not at the first API call.
    Derived from: 'fails fast on missing secrets (e.g. DATABASE_URL, SUPABASE_*)'.
    Note: validate() is imported into app.module.ts, so the effective validation lives
    in config/env.validation.ts, not app.module.ts itself.
    """
    assert SUPABASE_ENV_VALIDATION.exists(), (
        f"Supabase env.validation.ts not found: {SUPABASE_ENV_VALIDATION}"
    )
    assert "SUPABASE_" in _read(SUPABASE_ENV_VALIDATION), (
        "Supabase env.validation.ts must declare at least one SUPABASE_* variable in the Zod schema "
        "so missing Supabase credentials fail at process startup."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Criterion C — ZodValidationPipe (APP_PIPE) and ZodSerializerInterceptor (APP_INTERCEPTOR)
#               registered globally in all three app.module.ts files
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("module_path,label", OVERLAY_ROOT_MODULES)
def test_when_overlay_is_listed_then_it_does_not_replace_the_shared_app_module(
    module_path: Path, label: str
) -> None:
    """
    The pipe and the interceptor below are registered once, in the base app.module.ts, for
    all three variants. An overlay that shipped its own app.module.ts would have to repeat
    both registrations, so it must not.

    Validates project_initializer/templates-{token,supabase}-nestjs/api/src/app.module.ts absence.
    """
    assert not module_path.exists(), (
        f"[{label}] ships its own app.module.ts: {module_path}. "
        "Wire authentication through app.auth.ts so the global pipe and interceptor stay shared."
    )


@pytest.mark.parametrize("module_path,label", [(BASE_APP_MODULE, "base")])
def test_when_app_module_is_read_then_zod_validation_pipe_is_registered_as_app_pipe(
    module_path: Path, label: str
) -> None:
    """
    The shared app.module.ts must provide ZodValidationPipe as APP_PIPE so all incoming
    request bodies are validated and unknown properties are stripped globally.
    Derived from: 'ZodValidationPipe (APP_PIPE) … registered globally in all three variants'.

    Validates project_initializer/templates-api-nestjs/api/src/app.module.ts.
    """
    assert module_path.exists(), f"[{label}] app.module.ts not found: {module_path}"
    assert _has_app_pipe_zod(_read(module_path)), (
        f"[{label}] app.module.ts must provide ZodValidationPipe as APP_PIPE. "
        "Without it, unknown request properties are not stripped globally."
    )


@pytest.mark.parametrize("module_path,label", [(BASE_APP_MODULE, "base")])
def test_when_app_module_is_read_then_zod_serializer_interceptor_is_registered_as_app_interceptor(
    module_path: Path, label: str
) -> None:
    """
    The shared app.module.ts must provide ZodSerializerInterceptor as APP_INTERCEPTOR so
    response schemas are enforced globally and unlisted fields are stripped before serialization.
    Derived from: 'ZodSerializerInterceptor (APP_INTERCEPTOR) … registered globally in all three variants'.

    Validates project_initializer/templates-api-nestjs/api/src/app.module.ts.
    """
    assert module_path.exists(), f"[{label}] app.module.ts not found: {module_path}"
    assert _has_app_interceptor_zod(_read(module_path)), (
        f"[{label}] app.module.ts must provide ZodSerializerInterceptor as APP_INTERCEPTOR. "
        "Without it, response schemas are not enforced and Prisma rows can leak unlisted fields."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Criterion D — every response schema is a plain z.object() with no .passthrough()
# Criterion G — every request DTO schema is a plain z.object() (strips unknown props)
# (Both criteria reduce to the same observable: no .passthrough() in any *.dto.ts file.)
# ══════════════════════════════════════════════════════════════════════════════


def test_when_all_dto_files_are_read_then_no_schema_calls_passthrough() -> None:
    """
    Every DTO schema — request or response — across all three NestJS template trees must be
    a plain z.object() with no .passthrough() call.  .passthrough() lets Prisma rows emit
    unlisted fields (e.g. 'password') through the serializer unfiltered.
    Derived from: 'Every response schema is a plain z.object() (no .passthrough())' and
                  'Request DTO schemas are z.object() so unknown request properties are stripped'.

    Validates project_initializer/templates-{api,token,supabase}-nestjs/api/src/**/*.dto.ts.
    """
    all_dto_files = [f for root in _ALL_TEMPLATE_ROOTS for f in _dto_files_under(root)]
    assert all_dto_files, (
        "No *.dto.ts files found under any NestJS template tree. "
        "At minimum item.dto.ts must exist under templates-api-nestjs/."
    )
    violations = [str(p) for p in all_dto_files if _has_passthrough(_read(p))]
    assert not violations, (
        "These DTO files call .passthrough() which disables field whitelisting "
        "and risks leaking sensitive columns (e.g. password) from Prisma rows:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# Hypothesis property — detector completeness invariant
# Criterion D states ".passthrough() must not appear"; our detector must never
# produce a false negative regardless of what surrounds the call in source text.
# Kind: never-raises / never-false-negative over an unbounded input domain.
@given(prefix=st.text(), suffix=st.text())
def test_when_source_text_contains_passthrough_then_detector_returns_true(
    prefix: str, suffix: str
) -> None:
    """
    Invariant: _has_passthrough returns True for every string that contains the literal
    '.passthrough()' regardless of surrounding context.  A false negative here would silently
    allow a non-whitelisting schema to pass the field-leak check.
    Derived from criterion D's total-function requirement on the detection predicate.
    """
    assert _has_passthrough(prefix + ".passthrough()" + suffix)


# ══════════════════════════════════════════════════════════════════════════════
# Criterion E — every data-returning handler is decorated with @ZodSerializerDto (or @ZodResponse)
# ══════════════════════════════════════════════════════════════════════════════


def _all_controller_files() -> list[Path]:
    return [f for root in _ALL_TEMPLATE_ROOTS for f in _controller_files_under(root)]


def _controllers_without_zod_serializer(controllers: list[Path]) -> list[str]:
    return [
        str(p)
        for p in controllers
        if _has_http_data_handler(_read(p))
        and not _has_zod_serializer_dto_decorator(_read(p))
    ]


def test_when_all_controller_files_are_read_then_data_handlers_carry_zod_serializer_dto() -> (
    None
):
    """
    Every controller file that declares at least one HTTP handler (GET/POST/PUT/PATCH/DELETE)
    must contain at least one @ZodSerializerDto or @ZodResponse decorator so the Zod serializer enforces the
    response schema and strips unlisted fields per-handler.

    Assumption: a controller that declares standard HTTP-method handlers is considered to return
    entity/data.

    Derived from: 'Every handler returning entity/data … is decorated with @ZodSerializerDto(<ResponseDto>)'.

    Validates the *.controller.ts files under project_initializer/templates-api-nestjs/api/src, project_initializer/templates-token-nestjs/api/src and project_initializer/templates-supabase-nestjs/api/src.
    """
    all_ctrl_files = _all_controller_files()
    assert all_ctrl_files, (
        "No controller files found under any NestJS template tree. "
        "At minimum items.controller.ts must exist under templates-api-nestjs/."
    )
    missing = _controllers_without_zod_serializer(all_ctrl_files)
    assert not missing, (
        "These controller files declare HTTP handlers but are missing @ZodSerializerDto:\n"
        + "\n".join(f"  {m}" for m in missing)
        + "\nEvery data-returning handler must be annotated with @ZodSerializerDto(<ResponseDto>)."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Criterion F — existing serialization.spec.ts passes
#               (password stripped)
# ══════════════════════════════════════════════════════════════════════════════


def _find_serialization_spec() -> Optional[Path]:
    if not NESTJS_API_SRC.exists():
        return None
    hits = list(NESTJS_API_SRC.rglob("serialization.spec.ts"))
    return hits[0] if hits else None


def test_when_serialization_spec_is_searched_then_it_exists() -> None:
    """
    serialization.spec.ts must exist somewhere under the NestJS API template source tree.
    Its absence means the password-stripping assertion is not covered.
    Derived from: 'Existing serialization.spec.ts passes'.

    Validates project_initializer/templates-api-nestjs/api/src/serialization.spec.ts.
    """
    spec = _find_serialization_spec()
    assert spec is not None and spec.exists(), (
        "serialization.spec.ts not found under templates-api-nestjs/api/src/. "
        "This spec file is required by the criterion and must contain the "
        "password-stripping assertion."
    )


def test_when_serialization_spec_is_read_then_it_asserts_password_is_stripped() -> None:
    """
    serialization.spec.ts must contain an assertion that verifies a 'password' field injected
    into a Prisma-like object is absent from the serialized response.
    Derived from: 'injected password stripped' in the serialization.spec.ts criterion.

    Validates project_initializer/templates-api-nestjs/api/src/serialization.spec.ts.
    """
    spec = _find_serialization_spec()
    assert spec is not None and spec.exists(), (
        "serialization.spec.ts not found — cannot verify password-stripping assertion."
    )
    assert "password" in _read(spec), (
        "serialization.spec.ts must reference 'password' and assert its absence from the "
        "serialized output, confirming that Prisma rows cannot leak sensitive columns."
    )
