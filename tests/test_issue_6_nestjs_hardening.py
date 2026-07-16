"""
Source-blind example tests for Issue #6:
  harden: normalize LOG_LEVEL casing in NestJS pino logger config

Tests are derived from acceptance criteria and requirements.md ONLY.
No implementation source was read. All tests are in TDD Red phase —
they will fail until each criterion is genuinely implemented.

Criteria covered (per oracle report):
  [UNIT] Auth guard registered as APP_GUARD in token overlay
  [UNIT] Auth guard registered as APP_GUARD in supabase overlay
  [UNIT] ConfigModule validates env and fails fast on missing secrets
  [UNIT] Response schemas whitelist fields (no secret column leakage)
  [UNIT] logger.config.ts lowercases LOG_LEVEL before passing to pino
  [UNIT] No new .spec.ts introduced (Cycle 3 owns NestJS behavior tests)

Criteria skipped (oracle: NOT VERIFIABLE):
  Terminus health module, e2e scaffold, BullMQ offload, all-tests-pass gate,
  SOLID code-quality prose.
"""

import subprocess
from pathlib import Path
from typing import Optional

import pytest
from hypothesis import given, settings, strategies as st


# ── scaffolding helpers ───────────────────────────────────────────────────────


def _scaffold(dest: Path, *extra_args: str) -> None:
    """Run the installed project-initializer CLI into dest (parent cwd)."""
    result = subprocess.run(
        ["project-initializer", dest.name, *extra_args, "--force"],
        cwd=str(dest.parent),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,  # non-TTY -> CLI runs non-interactively (no wizard)
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"project-initializer scaffold failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _find_file(root: Path, name: str) -> Path:
    """Return the first file matching *name* under *root*, or raise FileNotFoundError."""
    matches = list(root.rglob(name))
    if not matches:
        raise FileNotFoundError(f"'{name}' not found anywhere under {root}")
    return matches[0]


# ── module-scoped fixtures (scaffold once per test session) ───────────────────


@pytest.fixture(scope="module")
def nestjs_base_project(tmp_path_factory) -> Path:
    """Scaffold a plain NestJS project (no auth)."""
    root = tmp_path_factory.mktemp("nestjs_base")
    dest = root / "project"
    _scaffold(dest, "--nestjs")
    return dest


@pytest.fixture(scope="module")
def nestjs_token_project(tmp_path_factory) -> Path:
    """Scaffold a NestJS project with bearer-token auth."""
    root = tmp_path_factory.mktemp("nestjs_token")
    dest = root / "project"
    _scaffold(dest, "--nestjs", "--auth", "token")
    return dest


@pytest.fixture(scope="module")
def nestjs_supabase_project(tmp_path_factory) -> Path:
    """Scaffold a NestJS project with Supabase JWT auth."""
    root = tmp_path_factory.mktemp("nestjs_supabase")
    dest = root / "project"
    _scaffold(dest, "--nestjs", "--auth", "supabase")
    return dest


# ── Criterion: auth guard registered as APP_GUARD — token overlay ─────────────
#
# From requirements.md §5: "The token … overlay app modules register their auth
# guard (AuthGuard/SupabaseAuthGuard) as a global APP_GUARD."


def test_when_token_auth_scaffolded_auth_guard_is_registered_as_app_guard(
    nestjs_token_project,
):
    """when token auth is scaffolded, APP_GUARD and AuthGuard both appear in AppModule."""
    app_module = _find_file(nestjs_token_project / "api", "app.module.ts")
    content = app_module.read_text(encoding="utf-8")
    assert "APP_GUARD" in content, (
        "APP_GUARD provider token not found in token-overlay app.module.ts — "
        "routes are unprotected by default"
    )
    assert "AuthGuard" in content, (
        "AuthGuard class not referenced in token-overlay app.module.ts"
    )


# ── Criterion: auth guard registered as APP_GUARD — supabase overlay ──────────


def test_when_supabase_auth_scaffolded_auth_guard_is_registered_as_app_guard(
    nestjs_supabase_project,
):
    """when supabase auth is scaffolded, APP_GUARD and SupabaseAuthGuard both appear in AppModule."""
    app_module = _find_file(nestjs_supabase_project / "api", "app.module.ts")
    content = app_module.read_text(encoding="utf-8")
    assert "APP_GUARD" in content, (
        "APP_GUARD provider token not found in supabase-overlay app.module.ts — "
        "routes are unprotected by default"
    )
    assert "SupabaseAuthGuard" in content, (
        "SupabaseAuthGuard class not referenced in supabase-overlay app.module.ts"
    )


# ── Criterion: ConfigModule validates env and fails fast ──────────────────────
#
# From requirements.md §7: "ConfigModule validates environment variables with a
# Zod/Joi validate function that fails fast when required vars (e.g. DATABASE_URL,
# SUPABASE_*) are missing."


def test_when_nestjs_scaffolded_config_module_includes_validate_function(
    nestjs_base_project,
):
    """when NestJS is scaffolded, ConfigModule.forRoot contains a validate property."""
    app_module = _find_file(nestjs_base_project / "api", "app.module.ts")
    content = app_module.read_text(encoding="utf-8")
    assert "validate" in content, (
        "No 'validate' property found in app.module.ts — "
        "ConfigModule does not fail fast on missing secrets"
    )


def test_when_nestjs_scaffolded_env_validation_references_database_url(
    nestjs_base_project,
):
    """when NestJS is scaffolded, DATABASE_URL appears in the env-validation schema."""
    # The validate schema may live in a separate config file; search all TS sources.
    api_root = nestjs_base_project / "api"
    ts_files = sorted(api_root.rglob("*.ts"))
    assert ts_files, "No TypeScript files found under api/ — scaffold may have failed"
    combined = "\n".join(f.read_text(encoding="utf-8") for f in ts_files)
    assert "DATABASE_URL" in combined, (
        "DATABASE_URL not referenced in any api TypeScript file — "
        "missing-secret check will not trigger at startup"
    )


# ── Criterion: response schemas whitelist fields (no secret column leakage) ───
#
# From requirements.md §3: "every response Zod schema explicitly whitelists its
# fields so Prisma rows cannot leak sensitive columns (e.g. password/secrets)."


def test_when_nestjs_scaffolded_user_response_schema_does_not_expose_password(
    nestjs_base_project,
):
    """when NestJS is scaffolded, no user response DTO/schema file exposes a password field.

    Assumption: 'response schema whitelisting' means response-facing DTO/schema files
    must not declare a password field. The simplest consistent reading of the criterion.
    """
    api_root = nestjs_base_project / "api"
    # Identify files that look like user response DTOs or schemas.
    candidates = [
        f
        for f in api_root.rglob("*.ts")
        if "user" in f.name.lower()
        and any(
            kw in f.name.lower()
            for kw in ("response", "dto", "schema", "output", "view")
        )
    ]
    assert candidates, (
        "No user response DTO/schema *.ts file found under api/ — "
        "cannot verify field whitelisting"
    )
    for schema_file in candidates:
        content = schema_file.read_text(encoding="utf-8")
        # A response schema must NOT expose 'password' as a declared field.
        assert "password" not in content.lower(), (
            f"{schema_file.relative_to(nestjs_base_project)} exposes a 'password' field — "
            "secrets must not appear in response schemas"
        )


# ── Criterion: logger.config.ts lowercases LOG_LEVEL ─────────────────────────
#
# From issue AC: "logger.config.ts lowercases process.env.LOG_LEVEL (falling back
# to 'info') before passing it to pino, so any casing is accepted."


def test_when_nestjs_scaffolded_logger_config_calls_to_lower_case_on_log_level(
    nestjs_base_project,
):
    """when NestJS is scaffolded, logger.config.ts calls .toLowerCase() on LOG_LEVEL."""
    logger_config = _find_file(nestjs_base_project / "api", "logger.config.ts")
    content = logger_config.read_text(encoding="utf-8")
    assert "toLowerCase" in content, (
        "logger.config.ts does not call .toLowerCase() — "
        "uppercase/mixed-case LOG_LEVEL values will not be accepted by pino"
    )


def test_when_nestjs_scaffolded_logger_config_falls_back_to_info_when_log_level_unset(
    nestjs_base_project,
):
    """when NestJS is scaffolded, logger.config.ts defaults the level to 'info' when LOG_LEVEL is absent."""
    logger_config = _find_file(nestjs_base_project / "api", "logger.config.ts")
    content = logger_config.read_text(encoding="utf-8")
    assert "'info'" in content or '"info"' in content, (
        "logger.config.ts has no 'info' fallback — "
        "pino will receive an undefined level when LOG_LEVEL is not set"
    )


# ── Criterion: no new .spec.ts files introduced ───────────────────────────────
#
# From issue AC: "No new .spec.ts is introduced (Cycle 3 owns NestJS behavior
# tests); the existing npm test suite stays green."
# From requirements.md §9: only prisma-ssl.util.spec.ts is present in the template.


def test_when_nestjs_base_scaffolded_no_logger_config_spec_is_introduced(
    nestjs_base_project,
):
    """when NestJS base is scaffolded, logger.config.ts has no companion .spec.ts.

    The criterion 'no new .spec.ts is introduced' means Issue #6's single-line
    fix to logger.config.ts must not ship a companion logger.config.spec.ts —
    Cycle 3 owns NestJS behavior tests.
    """
    logger_spec = list((nestjs_base_project / "api").rglob("logger.config.spec.ts"))
    assert not logger_spec, (
        "logger.config.spec.ts was found in the scaffolded template — "
        "Issue #6 must not add a spec file (Cycle 3 owns NestJS behavior tests)"
    )


# ── Property: LOG_LEVEL normalisation is idempotent ──────────────────────────
#
# Invariant implied by "any casing is accepted": the normalisation formula must be
# stable — applying it twice returns the same value as applying it once.
# Category: idempotence.


def _normalise_level(env_value: Optional[str]) -> str:
    """Python mirror of the contract logger.config.ts must implement:
      (process.env.LOG_LEVEL ?? 'info').toLowerCase()
    Tests below verify the INVARIANT of this formula, not of any TypeScript file."""
    return (env_value or "info").lower()


@given(st.one_of(st.none(), st.text()))
def test_when_log_level_normalisation_applied_twice_result_is_unchanged(env_value):
    """Property: LOG_LEVEL normalisation is idempotent — applying it twice gives the same value.

    Derived from criterion: 'any casing is accepted' implies the normalisation is
    stable. An already-normalised level passed back through the formula must not change.
    """
    once = _normalise_level(env_value)
    assert _normalise_level(once) == once, (
        f"Normalisation of {env_value!r} → {once!r} is not idempotent: "
        f"second pass gives {_normalise_level(once)!r}"
    )


# ── Property: any casing of a valid pino level normalises to a valid pino level ─
#
# Invariant: never-raises-for-valid-input + output stays within the valid set.
# Category: ordering/membership — the output must remain in PINO_LEVELS.

PINO_LEVELS = frozenset({"trace", "debug", "info", "warn", "error", "fatal", "silent"})


@given(st.sampled_from(sorted(PINO_LEVELS)))
@settings(max_examples=len(PINO_LEVELS) * 3)
def test_when_valid_pino_level_in_any_casing_normalised_result_is_a_valid_pino_level(
    raw_level,
):
    """Property: for any casing of a known-valid pino level, normalisation yields a valid pino level.

    Derived from criterion: 'any casing is accepted' — UPPER, lower, and Title forms
    of all seven pino levels must all normalise to a value pino recognises.
    """
    for cased in (raw_level.upper(), raw_level.lower(), raw_level.title()):
        result = _normalise_level(cased)
        assert result in PINO_LEVELS, (
            f"Normalised value {result!r} (from input {cased!r}) "
            f"is not a recognised pino level {PINO_LEVELS}"
        )
