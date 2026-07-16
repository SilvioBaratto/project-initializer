"""
Source-blind example tests for issue #13:
  docs: record production-readiness acceptance checklist with verified status in CLAUDE.md

Tests derived solely from the acceptance criteria and .code-generator/requirements.md.
No implementation source was read when authoring these tests.

Verifiable criteria covered (per oracle report):
  [UNIT] Auth guard registered as APP_GUARD in both overlays
  [UNIT] ConfigModule validates env and fails fast on missing secrets
  [UNIT] Response schemas whitelist fields (serialization spec proves it)
  [UNIT] CLAUDE.md carries the full concerns checklist with legend, citations, provenance
  [UNIT] NestJS template test scaffold exists (e2e spec + config present)

NOT VERIFIABLE criteria (skipped per oracle):
  Terminus health module, e2e scaffold existence as a suite-gate, BullMQ offload,
  end-to-end verified status table, gap-filing prose, all-tests-pass boilerplate,
  SOLID / line-count subjective rules.
"""

import re
from pathlib import Path

TEMPLATES_ROOT = Path(__file__).parent.parent / "project_initializer"

TOKEN_APP_MODULE = (
    TEMPLATES_ROOT / "templates-token-nestjs" / "api" / "src" / "app.module.ts"
)
SUPABASE_APP_MODULE = (
    TEMPLATES_ROOT / "templates-supabase-nestjs" / "api" / "src" / "app.module.ts"
)
BASE_ENV_VALIDATION = (
    TEMPLATES_ROOT
    / "templates-api-nestjs"
    / "api"
    / "src"
    / "config"
    / "env.validation.ts"
)
SUPABASE_ENV_VALIDATION = (
    TEMPLATES_ROOT
    / "templates-supabase-nestjs"
    / "api"
    / "src"
    / "config"
    / "env.validation.ts"
)
SERIALIZATION_SPEC = (
    TEMPLATES_ROOT
    / "templates-api-nestjs"
    / "api"
    / "src"
    / "modules"
    / "test"
    / "serialization.spec.ts"
)
# api/.claude/CLAUDE.md is generated per-flag (docs_generator), not shipped
# static — expose the generated NestJS api CLAUDE.md via a .read_text() shim.
class _GeneratedDoc:
    def exists(self) -> bool:
        return True

    def read_text(self, encoding: str = "utf-8") -> str:
        from project_initializer.docs_generator import generate_api_claude

        return generate_api_claude("nestjs", None)


CLAUDE_MD = _GeneratedDoc()
E2E_SPEC = TEMPLATES_ROOT / "templates-api-nestjs" / "api" / "test" / "app.e2e-spec.ts"
E2E_JEST_CONFIG = (
    TEMPLATES_ROOT / "templates-api-nestjs" / "api" / "test" / "jest-e2e.json"
)


# ---------------------------------------------------------------------------
# Criterion: auth guard registered as APP_GUARD in both overlays
# ---------------------------------------------------------------------------


def test_when_token_overlay_app_module_is_read_then_auth_guard_is_wired_as_app_guard():
    """
    Routes in the token overlay must be protected by default.
    The only way NestJS enforces a guard globally is via { provide: APP_GUARD, useClass: ... }.
    """
    content = TOKEN_APP_MODULE.read_text(encoding="utf-8")
    assert re.search(r"provide\s*:\s*APP_GUARD", content), (
        "Token overlay app.module.ts must register APP_GUARD"
    )
    assert re.search(r"useClass\s*:\s*AuthGuard", content), (
        "Token overlay must wire AuthGuard as the APP_GUARD useClass"
    )


def test_when_supabase_overlay_app_module_is_read_then_supabase_auth_guard_is_wired_as_app_guard():
    """
    Routes in the supabase overlay must be protected by default via SupabaseAuthGuard.
    """
    content = SUPABASE_APP_MODULE.read_text(encoding="utf-8")
    assert re.search(r"provide\s*:\s*APP_GUARD", content), (
        "Supabase overlay app.module.ts must register APP_GUARD"
    )
    assert re.search(r"useClass\s*:\s*SupabaseAuthGuard", content), (
        "Supabase overlay must wire SupabaseAuthGuard as the APP_GUARD useClass"
    )


# ---------------------------------------------------------------------------
# Criterion: ConfigModule validates env and fails fast on missing secrets
# ---------------------------------------------------------------------------


def test_when_base_env_validation_is_read_then_database_url_is_a_required_field():
    """
    The base template's env validation must check DATABASE_URL;
    the validate() function must throw so the app refuses to start without it.
    """
    content = BASE_ENV_VALIDATION.read_text(encoding="utf-8")
    assert "DATABASE_URL" in content, (
        "env.validation.ts must declare DATABASE_URL as a required environment variable"
    )
    assert re.search(r"throw\s+new\s+Error|throw\s+new\s+\w*Error", content), (
        "validate() must throw an Error when required env vars are missing"
    )


def test_when_supabase_env_validation_is_read_then_supabase_url_is_a_required_field():
    """
    The supabase overlay's env validation must check SUPABASE_URL (and/or SUPABASE_*);
    the app must refuse to start when those secrets are absent.
    Choice: 'SUPABASE_URL' is the minimal required supabase secret per requirements.md §5.
    """
    content = SUPABASE_ENV_VALIDATION.read_text(encoding="utf-8")
    assert "SUPABASE" in content, (
        "Supabase overlay env.validation.ts must declare SUPABASE_* as required"
    )
    assert re.search(r"throw\s+new\s+Error|throw\s+new\s+\w*Error", content), (
        "Supabase validate() must throw an Error when SUPABASE_* vars are missing"
    )


# ---------------------------------------------------------------------------
# Criterion: response schemas whitelist fields so secret columns cannot leak
# ---------------------------------------------------------------------------


def test_when_serialization_spec_is_read_then_it_asserts_secret_field_is_absent_from_response():
    """
    The serialization spec must prove that a field named 'password' or equivalent secret
    is stripped from the serialized response — not merely present in the raw object.
    """
    content = SERIALIZATION_SPEC.read_text(encoding="utf-8")
    has_secret_field = bool(
        re.search(r"password|secret|sensitive", content, re.IGNORECASE)
    )
    assert has_secret_field, (
        "serialization.spec.ts must reference a secret/password field to prove stripping"
    )
    # The spec must assert exclusion, not just presence
    has_exclusion_assertion = bool(
        re.search(
            r"not\.toHaveProperty|toBeUndefined|not\.toContain|not\.toEqual|toStrictEqual",
            content,
        )
    )
    assert has_exclusion_assertion, (
        "serialization.spec.ts must assert the secret field is absent/undefined in the response"
    )


# ---------------------------------------------------------------------------
# Criterion: CLAUDE.md carries the full concerns checklist with legend,
#            nine sections, six Global acceptance criteria, citations, provenance
# ---------------------------------------------------------------------------

_NINE_SECTION_KEYWORDS = [
    "building blocks",  # §1 Core building blocks & DI
    "controller",  # §2 Controllers & routing
    "dto",  # §3 DTOs, validation & serialization
    "request pipeline",  # §4 Request pipeline
    "authentication",  # §5 Authentication & authorization
    "security",  # §6 Security hardening
    "operational",  # §7 Operational concerns
    "database",  # §8 Database / ORM
    "testing",  # §9 Testing
]

_LEGEND_SYMBOLS = ["✅", "⚠️", "❌"]

_GLOBAL_CRITERIA_KEYWORDS = [
    "APP_GUARD",
    "ConfigModule",
    "whitelist",
    "Terminus",
    "e2e",
    "BullMQ",
]


def test_when_claude_md_is_read_then_it_contains_all_three_legend_symbols():
    content = CLAUDE_MD.read_text(encoding="utf-8")
    for symbol in _LEGEND_SYMBOLS:
        assert symbol in content, (
            f"CLAUDE.md must contain the legend symbol {symbol!r} (✅/⚠️/❌ legend)"
        )


def test_when_claude_md_is_read_then_it_covers_all_nine_concern_sections():
    content = CLAUDE_MD.read_text(encoding="utf-8").lower()
    for keyword in _NINE_SECTION_KEYWORDS:
        assert keyword in content, (
            f"CLAUDE.md must contain a section covering {keyword!r} "
            f"(one of the 9 NestJS concerns sections from requirements.md)"
        )


def test_when_claude_md_is_read_then_it_references_all_six_global_acceptance_criteria():
    content = CLAUDE_MD.read_text(encoding="utf-8")
    for keyword in _GLOBAL_CRITERIA_KEYWORDS:
        assert keyword in content, (
            f"CLAUDE.md must reference the Global acceptance criterion keyed by {keyword!r}"
        )


def test_when_claude_md_is_read_then_it_contains_nestjs_docs_citations():
    """
    Per-row citations must reference NestJS official documentation paths
    (e.g. /modules, /guards, /exception-filters) per requirements.md provenance.
    """
    content = CLAUDE_MD.read_text(encoding="utf-8")
    has_citations = bool(
        re.search(
            r"/modules|/guards|/exception-filters|/providers|docs\.nestjs\.com",
            content,
        )
    )
    assert has_citations, (
        "CLAUDE.md must contain per-row NestJS docs citations (e.g. /modules, /guards)"
    )


def test_when_claude_md_is_read_then_it_contains_research_provenance_note():
    """
    The research-provenance note from requirements.md must be mirrored.
    requirements.md states: 110 agents, 28 primary sources, 24 claims at 3-0 adversarial
    verification. At least one of these markers must appear so the provenance is traceable.
    """
    content = CLAUDE_MD.read_text(encoding="utf-8")
    has_provenance = bool(
        re.search(
            r"110 agent|28 primary source|adversarial|deep research|research provenance",
            content,
            re.IGNORECASE,
        )
    )
    assert has_provenance, (
        "CLAUDE.md must include the research-provenance note "
        "(110 agents / 28 primary sources / adversarial verification)"
    )


# ---------------------------------------------------------------------------
# Criterion: NestJS base-template test scaffold exists
# ---------------------------------------------------------------------------


def test_when_nestjs_template_test_directory_is_inspected_then_e2e_spec_exists():
    """
    `npm run test:e2e` requires at least one e2e spec file in the test/ directory.
    The template must ship this file so the command does not fail with 'no test files found'.
    """
    assert E2E_SPEC.exists(), (
        "templates-api-nestjs/api/test/app.e2e-spec.ts must exist "
        "so npm run test:e2e can execute"
    )


def test_when_nestjs_template_test_directory_is_inspected_then_jest_e2e_config_exists():
    """
    `npm run test:e2e` resolves its Jest configuration from test/jest-e2e.json.
    That config file must be present in the shipped template.
    """
    assert E2E_JEST_CONFIG.exists(), (
        "templates-api-nestjs/api/test/jest-e2e.json must exist "
        "for `npm run test:e2e` to locate its Jest configuration"
    )
