"""
Source-blind example tests for issue #10: Expose BullMQ queue monitoring with Bull Board.

Tests derived from acceptance criteria only (TDD Red phase).
No implementation source was read. Tests will fail until the implementation exists.

Hypothesis @given property tests: NONE authored.
  No criterion implies a round-trip, idempotence, never-raises, or ordering invariant
  over an unbounded input domain. Multi-value assertions (3 packages, 3 overlays) use
  @pytest.mark.parametrize over the finite set stated in the criterion.
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PI = REPO_ROOT / "project_initializer"

NESTJS_BASE = PI / "templates-api-nestjs" / "api"
NESTJS_TOKEN = PI / "templates-token-nestjs" / "api"
NESTJS_SUPABASE = PI / "templates-supabase-nestjs" / "api"

MONITORING_MODULE = (
    NESTJS_BASE / "src" / "modules" / "monitoring" / "monitoring.module.ts"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _package_deps(base: Path) -> dict:
    pkg = json.loads(_read(base / "package.json"))
    return {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}


# ---------------------------------------------------------------------------
# Criterion [UNIT] S1:
# @bull-board/api, @bull-board/nestjs, @bull-board/express are added
# (pinned) to api/package.json.
# ---------------------------------------------------------------------------

BULL_BOARD_PACKAGES = [
    "@bull-board/api",
    "@bull-board/nestjs",
    "@bull-board/express",
]


@pytest.mark.parametrize("pkg_name", BULL_BOARD_PACKAGES)
def test_when_package_json_is_read_then_bull_board_dep_is_present(pkg_name):
    deps = _package_deps(NESTJS_BASE)
    assert pkg_name in deps, (
        f"{pkg_name} must be declared in api/package.json (dependencies or devDependencies)"
    )


@pytest.mark.parametrize("pkg_name", BULL_BOARD_PACKAGES)
def test_when_bull_board_version_is_read_then_it_is_pinned(pkg_name):
    """
    A pinned version has no leading ^ or ~ (no semver range specifier).
    Criterion says 'pinned' — interpreted as an exact version string with no range prefix.
    """
    deps = _package_deps(NESTJS_BASE)
    version = deps.get(pkg_name, "")
    assert version, f"{pkg_name} must have a non-empty version in api/package.json"
    assert not version.startswith("^") and not version.startswith("~"), (
        f"{pkg_name}@{version} is not pinned — remove the ^ or ~ range prefix"
    )


# ---------------------------------------------------------------------------
# Criterion [T2] S2:
# A monitoring module mounts Bull Board (e.g. at /admin/queues) and
# registers the chat queue via BullMQAdapter.
# (Oracle: T2 / HTTP. Verified statically: the module source must contain
# the named symbols — a missing symbol means the criterion cannot be met.)
# ---------------------------------------------------------------------------


def test_when_monitoring_module_is_read_then_bull_mq_adapter_is_used():
    """
    BullMQAdapter is the class from @bull-board/api that wraps a BullMQ queue.
    Its presence confirms the monitoring module uses the correct Bull Board adapter.
    """
    content = _read(MONITORING_MODULE)
    assert "BullMQAdapter" in content


def test_when_monitoring_module_is_read_then_chat_queue_is_registered():
    """The chat queue name must appear in the monitoring module source."""
    content = _read(MONITORING_MODULE)
    assert "chat" in content


def test_when_monitoring_module_is_read_then_admin_queues_path_is_configured():
    """
    Bull Board must be mounted at /admin/queues.
    Assumption: '/admin/queues' is the mount path chosen per the criterion's example.
    """
    content = _read(MONITORING_MODULE)
    assert "/admin/queues" in content


# ---------------------------------------------------------------------------
# Criterion [UNIT] S3:
# The module is wired into app.module.ts for the base template and both
# auth overlays (token, supabase).
# ---------------------------------------------------------------------------

OVERLAY_APP_MODULES = [
    pytest.param(NESTJS_BASE / "src" / "app.module.ts", id="base"),
    pytest.param(NESTJS_TOKEN / "src" / "app.module.ts", id="token-overlay"),
    pytest.param(NESTJS_SUPABASE / "src" / "app.module.ts", id="supabase-overlay"),
]


@pytest.mark.parametrize("app_module_path", OVERLAY_APP_MODULES)
def test_when_app_module_is_read_then_monitoring_module_is_imported(app_module_path):
    content = _read(app_module_path)
    assert "MonitoringModule" in content, (
        f"MonitoringModule must appear in {app_module_path} imports"
    )


# ---------------------------------------------------------------------------
# Criterion [UNIT] S4:
# The dashboard route is reachable given setGlobalPrefix('api/v1'), and
# the auth-variant guard behavior (protected vs @Public() / local-only) is
# decided and documented inline in the module.
# ---------------------------------------------------------------------------


def test_when_main_ts_is_read_then_global_prefix_api_v1_is_set():
    """
    app.setGlobalPrefix('api/v1') must appear in main.ts so that
    /admin/queues is reachable under /api/v1/admin/queues.
    """
    content = _read(NESTJS_BASE / "src" / "main.ts")
    assert "setGlobalPrefix" in content
    assert "api/v1" in content


def test_when_monitoring_module_is_read_then_guard_behavior_is_documented_inline():
    """
    Criterion: guard behavior (protected vs @Public() / local-only) is
    'decided and documented inline in the module'.
    Assumption: at minimum one inline comment (// ...) in the module source
    references 'guard', '@Public', or 'auth'.
    """
    content = _read(MONITORING_MODULE)
    has_guard_comment = bool(
        re.search(r"//[^\n]*(guard|@Public|auth)", content, re.IGNORECASE)
    )
    assert has_guard_comment, (
        "monitoring.module.ts must contain an inline comment documenting the "
        "guard / @Public / auth decision for the Bull Board dashboard route"
    )


# ---------------------------------------------------------------------------
# Criterion [UNIT] S5:
# A spec asserts the monitoring module registers the chat queue feature.
# ---------------------------------------------------------------------------

MONITORING_SPEC = (
    NESTJS_BASE / "src" / "modules" / "monitoring" / "monitoring.module.spec.ts"
)


def test_when_monitoring_spec_exists_then_it_references_chat_queue():
    """
    Assumption: the spec is co-located with the module at
      src/modules/monitoring/monitoring.module.spec.ts
    (NestJS convention for a unit spec).
    """
    assert MONITORING_SPEC.exists(), (
        f"Spec file not found: {MONITORING_SPEC} — "
        "criterion requires a spec that asserts the chat queue feature"
    )
    content = _read(MONITORING_SPEC)
    assert "chat" in content.lower(), (
        "monitoring.module.spec.ts must reference the 'chat' queue"
    )


def test_when_monitoring_spec_is_read_then_it_uses_create_testing_module():
    """NestJS unit specs must bootstrap the module via Test.createTestingModule."""
    assert MONITORING_SPEC.exists()
    content = _read(MONITORING_SPEC)
    assert "createTestingModule" in content


# ---------------------------------------------------------------------------
# Global criterion [UNIT] G1:
# The auth guard is confirmed registered as APP_GUARD in both the token
# and supabase overlays, so routes are protected by default.
# ---------------------------------------------------------------------------

AUTH_OVERLAY_APP_MODULES = [
    pytest.param(NESTJS_TOKEN / "src" / "app.module.ts", id="token-overlay"),
    pytest.param(NESTJS_SUPABASE / "src" / "app.module.ts", id="supabase-overlay"),
]


@pytest.mark.parametrize("app_module_path", AUTH_OVERLAY_APP_MODULES)
def test_when_auth_overlay_app_module_is_read_then_app_guard_is_registered(
    app_module_path,
):
    """
    APP_GUARD must appear in the providers array so the guard fires on every
    route by default. This is the biggest security risk if absent.
    """
    content = _read(app_module_path)
    assert "APP_GUARD" in content, (
        f"APP_GUARD not found in {app_module_path} — auth guard must be global"
    )


# ---------------------------------------------------------------------------
# Global criterion [UNIT] G2:
# ConfigModule validates env and fails fast on missing secrets
# (e.g. DATABASE_URL, SUPABASE_*).
# ---------------------------------------------------------------------------


def test_when_base_app_module_is_read_then_config_module_has_validate_option():
    """
    ConfigModule.forRoot must be called with a 'validate' key so that missing
    env vars raise at startup rather than silently returning undefined.
    Assumption: validate is passed inline or imported and referenced in the
    forRoot({}) call that appears in app.module.ts.
    """
    content = _read(NESTJS_BASE / "src" / "app.module.ts")
    assert "ConfigModule" in content
    assert "validate" in content


def test_when_nestjs_src_is_scanned_then_database_url_appears_in_validation_schema():
    """
    The validation schema must cover DATABASE_URL so the app fails fast when
    it is absent. At least one .ts file in the api/src tree must reference it.
    """
    src_root = NESTJS_BASE / "src"
    ts_files = list(src_root.rglob("*.ts"))
    found = any("DATABASE_URL" in _read(f) for f in ts_files)
    assert found, (
        "DATABASE_URL must appear in at least one .ts source file "
        "(env validation schema) under templates-api-nestjs/api/src"
    )


# ---------------------------------------------------------------------------
# Global criterion [UNIT] G3:
# Response schemas whitelist fields so Prisma rows cannot leak secret columns
# through the serializer.
# ---------------------------------------------------------------------------


def test_when_base_app_module_is_read_then_zod_serializer_interceptor_is_registered():
    """
    ZodSerializerInterceptor (or APP_INTERCEPTOR) must be registered globally
    so every response is filtered through a Zod output schema.
    """
    content = _read(NESTJS_BASE / "src" / "app.module.ts")
    assert "ZodSerializerInterceptor" in content or "APP_INTERCEPTOR" in content, (
        "app.module.ts must register ZodSerializerInterceptor as APP_INTERCEPTOR"
    )


def test_when_response_schemas_are_scanned_then_password_field_is_absent_from_all():
    """
    Response schemas must not expose a 'password' field.
    Assumption: response schemas are .ts files whose names contain 'response'
    (NestJS convention). Each such file is checked independently.
    """
    src_root = NESTJS_BASE / "src"
    response_files = [f for f in src_root.rglob("*.ts") if "response" in f.name.lower()]
    for schema_file in response_files:
        content = _read(schema_file)
        assert "password" not in content, (
            f"{schema_file} is a response schema but exposes 'password' — "
            "Prisma rows must not leak secret columns through the serializer"
        )
