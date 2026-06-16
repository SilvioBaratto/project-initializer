"""
Source-blind example tests for Issue #11: lock Redis/BullMQ wiring across NestJS variants.

Derived solely from the acceptance criteria and requirements.md — no implementation
source was read.  Every test is in Red phase: it must FAIL until the criterion is met.

Hypothesis note: all verifiable criteria reduce to structural assertions on template
files (file-content, YAML shape).  None imply a function-level round-trip, idempotence,
never-raises, or ordering invariant over random input; no @given properties are emitted.
"""

import re
import yaml
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES = REPO_ROOT / "project_initializer"

NESTJS_BASE = TEMPLATES / "templates-api-nestjs"
NESTJS_TOKEN = TEMPLATES / "templates-token-nestjs"
NESTJS_SUPABASE = TEMPLATES / "templates-supabase-nestjs"

_APP_MODULE = Path("api/src/app.module.ts")
_ENV_VALIDATION = Path("api/src/config/env.validation.ts")
_DOCKER_COMPOSE = Path("docker-compose.yml")


# ── helpers ───────────────────────────────────────────────────────────────────


def _read(template_dir: Path, rel: Path) -> str:
    path = template_dir / rel
    assert path.exists(), f"Expected template file not found: {path}"
    return path.read_text(encoding="utf-8")


def _parse_compose(template_dir: Path) -> dict:
    return yaml.safe_load(_read(template_dir, _DOCKER_COMPOSE))


# ── auth guard registered as APP_GUARD (biggest security risk if missing) ─────


def test_when_token_overlay_app_module_is_read_then_auth_guard_is_registered_as_app_guard():
    """AuthGuard must appear as the useClass of an APP_GUARD provider so every route is
    protected by default; opt-out is only via @Public()."""
    content = _read(NESTJS_TOKEN, _APP_MODULE)
    assert "APP_GUARD" in content, "token overlay app.module.ts must register APP_GUARD"
    assert "AuthGuard" in content, (
        "token overlay app.module.ts must reference AuthGuard"
    )


def test_when_supabase_overlay_app_module_is_read_then_supabase_auth_guard_is_registered_as_app_guard():
    """SupabaseAuthGuard must appear as the useClass of an APP_GUARD provider so every
    route is protected by default; opt-out is only via @Public()."""
    content = _read(NESTJS_SUPABASE, _APP_MODULE)
    assert "APP_GUARD" in content, (
        "supabase overlay app.module.ts must register APP_GUARD"
    )
    assert "SupabaseAuthGuard" in content, (
        "supabase overlay app.module.ts must reference SupabaseAuthGuard"
    )


# ── ConfigModule validates env secrets and fails fast ─────────────────────────


def test_when_base_app_module_is_read_then_config_module_receives_a_validate_function():
    """ConfigModule.forRoot must receive a validate: function so that missing env vars
    abort startup immediately rather than causing silent runtime failures."""
    content = _read(NESTJS_BASE, _APP_MODULE)
    assert "ConfigModule" in content, "app.module.ts must import ConfigModule"
    assert "validate" in content, (
        "ConfigModule.forRoot must pass a validate function for fast-fail env validation"
    )


def test_when_base_env_validation_file_is_read_then_database_url_is_a_required_field():
    """env.validation must declare DATABASE_URL as required so a missing value is caught
    at application startup."""
    content = _read(NESTJS_BASE, _ENV_VALIDATION)
    assert "DATABASE_URL" in content, "env.validation must validate DATABASE_URL"


def test_when_supabase_overlay_env_validation_is_read_then_supabase_url_is_a_required_field():
    """Supabase env.validation must declare SUPABASE_URL as required; the supabase overlay
    replaces local-DB config with Supabase-hosted config."""
    content = _read(NESTJS_SUPABASE, _ENV_VALIDATION)
    assert "SUPABASE_URL" in content, (
        "supabase env.validation must validate SUPABASE_URL"
    )


# ── response schemas whitelist fields (no password leak through serialiser) ───


def test_when_response_dtos_are_scanned_then_no_password_field_is_exposed():
    """All response DTO/schema files in the base NestJS template must not expose a
    'password' field — Prisma rows must never leak secret columns through the serialiser.
    Scans all *.dto.ts files under templates-api-nestjs/api/src/ and fails if any
    response-facing schema declares a 'password' property."""
    src_dir = NESTJS_BASE / "api" / "src"
    assert src_dir.exists(), f"Expected NestJS src directory not found: {src_dir}"
    dto_files = list(src_dir.rglob("*.dto.ts"))
    assert dto_files, "No *.dto.ts files found under templates-api-nestjs/api/src/"
    for dto_file in dto_files:
        content = dto_file.read_text(encoding="utf-8")
        assert not re.search(r"\bpassword\b\s*:", content), (
            f"{dto_file.name} exposes a 'password' field in a DTO schema — "
            "Prisma rows must not leak secret columns through the serialiser"
        )


# ── BullModule.forRoot wired with REDIS_HOST / REDIS_PORT ─────────────────────


def test_when_base_app_module_is_read_then_bull_module_is_registered_with_redis_env_vars():
    """Base app.module.ts must register BullModule using forRoot or forRootAsync and
    source the Redis connection from REDIS_HOST / REDIS_PORT config values."""
    content = _read(NESTJS_BASE, _APP_MODULE)
    assert "BullModule" in content, "app.module.ts must import BullModule"
    assert re.search(r"forRoot(Async)?", content), (
        "BullModule must use forRoot or forRootAsync to configure the connection"
    )
    assert "REDIS_HOST" in content, "BullModule config must reference REDIS_HOST"
    assert "REDIS_PORT" in content, "BullModule config must reference REDIS_PORT"


@pytest.mark.parametrize(
    "overlay_dir,label",
    [
        (NESTJS_TOKEN, "token"),
        (NESTJS_SUPABASE, "supabase"),
    ],
)
def test_when_auth_overlay_app_module_is_read_then_bull_module_uses_redis_env_vars(
    overlay_dir: Path, label: str
) -> None:
    """Auth overlay app.module.ts must configure BullModule with REDIS_HOST / REDIS_PORT
    so the queue connection is environment-driven in all three NestJS variants."""
    content = _read(overlay_dir, _APP_MODULE)
    assert "BullModule" in content, (
        f"{label} overlay app.module.ts must import BullModule"
    )
    assert "REDIS_HOST" in content, (
        f"{label} overlay app.module.ts must reference REDIS_HOST"
    )
    assert "REDIS_PORT" in content, (
        f"{label} overlay app.module.ts must reference REDIS_PORT"
    )


# ── env.validation accepts and defaults REDIS_HOST / REDIS_PORT ───────────────


def test_when_env_validation_is_evaluated_then_redis_host_defaults_to_localhost():
    """env.validation must declare REDIS_HOST with a default of 'localhost' so the app
    starts without explicit Redis config in local development."""
    content = _read(NESTJS_BASE, _ENV_VALIDATION)
    assert "REDIS_HOST" in content, "env.validation must declare REDIS_HOST"
    assert "localhost" in content, (
        "env.validation must provide 'localhost' as the default for REDIS_HOST"
    )


def test_when_env_validation_is_evaluated_then_redis_port_defaults_to_6379():
    """env.validation must declare REDIS_PORT with a default of 6379 so the app starts
    without explicit Redis config in local development."""
    content = _read(NESTJS_BASE, _ENV_VALIDATION)
    assert "REDIS_PORT" in content, "env.validation must declare REDIS_PORT"
    assert "6379" in content, (
        "env.validation must provide 6379 as the default for REDIS_PORT"
    )


# ── docker-compose defines redis service with api health dependency ───────────


@pytest.mark.parametrize(
    "template_dir,label",
    [
        (NESTJS_BASE, "base"),
        (NESTJS_SUPABASE, "supabase"),
    ],
)
def test_when_docker_compose_is_read_then_redis_service_is_defined(
    template_dir: Path, label: str
) -> None:
    """docker-compose.yml (base and supabase) must define a top-level 'redis' service."""
    compose = _parse_compose(template_dir)
    assert "redis" in compose.get("services", {}), (
        f"{label} docker-compose.yml must define a 'redis' service"
    )


@pytest.mark.parametrize(
    "template_dir,label",
    [
        (NESTJS_BASE, "base"),
        (NESTJS_SUPABASE, "supabase"),
    ],
)
def test_when_docker_compose_is_read_then_api_service_depends_on_redis_being_healthy(
    template_dir: Path, label: str
) -> None:
    """docker-compose.yml (base and supabase): the api service must declare
    depends_on: redis with condition: service_healthy so it never starts before Redis
    is ready to accept connections."""
    compose = _parse_compose(template_dir)
    api_service = compose.get("services", {}).get("api", {})
    assert api_service, f"{label} docker-compose.yml must define an 'api' service"

    depends_on = api_service.get("depends_on", {})
    if isinstance(depends_on, list):
        # Short-form depends_on: health-condition is not expressible, so fail.
        assert False, (
            f"{label} docker-compose.yml api.depends_on must use the long form "
            "(dict with condition: service_healthy) not the short list form"
        )
    redis_dep = depends_on.get("redis", {})
    assert redis_dep, f"{label} docker-compose.yml api.depends_on must include redis"
    assert redis_dep.get("condition") == "service_healthy", (
        f"{label} docker-compose.yml api.depends_on.redis.condition must be service_healthy"
    )


# ── queue-monitor module registered in app.module.ts ─────────────────────────


def test_when_base_app_module_is_read_then_queue_monitor_module_is_registered():
    """Base app.module.ts must import and register a queue-monitor module.
    Assumption: the module follows the conventional naming QueueMonitorModule or
    uses @bull-board/nestjs (BullBoardModule); either satisfies the criterion."""
    content = _read(NESTJS_BASE, _APP_MODULE)
    assert re.search(
        r"QueueMonitor\w*Module|BullBoard\w*Module|queue[-_]monitor",
        content,
        re.IGNORECASE,
    ), (
        "app.module.ts must register a queue-monitor module "
        "(e.g. QueueMonitorModule or BullBoardModule from @bull-board/nestjs)"
    )
