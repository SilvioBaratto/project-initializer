"""Generate variant-specific .env files from the root .env.

The generator is composed of small per-section builders (``_database_section``,
``_supabase_section``, ``_entra_section``, ``_token_section``, ``_server_section``,
``_redis_section``, ``_topology_section``, ``_llm_section``). Each returns a
``list[str]`` of ``KEY=VALUE`` / comment lines and is selected by the
framework/auth flags in :func:`generate_env`. Splitting the flat body into
sections keeps every variant's output explicit and testable.

Two kinds of variables are emitted, grouped into commented sub-sections:

* **app config** — read by the running app (``DATABASE_URL``, ``ENTRA_*``, ...).
* **compose topology** — read by ``docker-compose.yml`` to publish host ports
  (``API_HOST_PORT``, ``FRONTEND_HOST_PORT``, ``DB_HOST_PORT``). Compose consumes
  these as ``${VAR:-default}`` so an unset var falls back to today's fixed port.

Every value carries a working dev default so a freshly scaffolded project runs
``docker compose up`` with no edits; the generated ``.env`` and ``.env.example``
are byte-identical (placeholders double as dev defaults).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

# Callable[(key, fallback)] -> str, used by the private section builders.
_Lookup = Callable[..., str]

_DEFAULTS_PATH = Path(__file__).parent / "env_defaults.env"


def parse_env(env_path: Path) -> dict[str, str]:
    """Parse a .env file into a dict, skipping comments and blanks."""
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"')
    return env


def _database_section(val: _Lookup, *, is_fastapi: bool, is_supabase: bool) -> list[str]:
    """Emit the ``# Database`` block (app config).

    Supabase variants read Supabase-hosted connection strings; all others read
    the local Docker PostgreSQL URL. NestJS (Prisma) additionally needs a
    ``DIRECT_URL`` and quotes its values (Prisma parses the raw ``.env`` itself).
    """
    lines = ["# Database"]
    if is_supabase:
        if is_fastapi:
            lines.append(f"DATABASE_URL={val('SUPABASE_DATABASE_URL')}")
            lines.append(f"DIRECT_DATABASE_URL={val('SUPABASE_DIRECT_DATABASE_URL')}")
        else:
            lines.append(f'DATABASE_URL="{val("SUPABASE_DATABASE_URL_PRISMA")}"')
            lines.append(f'DIRECT_URL="{val("SUPABASE_DIRECT_URL")}"')
    else:
        if is_fastapi:
            lines.append(f"DATABASE_URL={val('DOCKER_DATABASE_URL')}")
        else:
            lines.append(f'DATABASE_URL="{val("DOCKER_DATABASE_URL_PRISMA")}"')
            lines.append(f'DIRECT_URL="{val("DOCKER_DIRECT_URL")}"')
    return lines


def _supabase_section(val: _Lookup) -> list[str]:
    """Emit the ``# Supabase`` client block (app config, supabase variants only)."""
    return [
        "",
        "# Supabase",
        f"SUPABASE_URL={val('SUPABASE_URL')}",
        f"SUPABASE_PUBLISHABLE_KEY={val('SUPABASE_PUBLISHABLE_KEY')}",
    ]


def _entra_section(val: _Lookup) -> list[str]:
    """Emit the ``# Microsoft Entra ID`` block (app config, entra variants only)."""
    return [
        "",
        "# Microsoft Entra ID",
        f"ENTRA_TENANT_ID={val('ENTRA_TENANT_ID')}",
        f"ENTRA_API_CLIENT_ID={val('ENTRA_API_CLIENT_ID')}",
        f"ENTRA_API_AUDIENCE={val('ENTRA_API_AUDIENCE')}",
        f"ENTRA_API_SCOPE={val('ENTRA_API_SCOPE')}",
        f"ENTRA_SPA_CLIENT_ID={val('ENTRA_SPA_CLIENT_ID')}",
    ]


def _token_section(val: _Lookup) -> list[str]:
    """Emit the ``# Authentication`` block (app config, token variants only)."""
    return [
        "",
        "# Authentication",
        f"AUTH_TOKEN={val('AUTH_TOKEN')}",
        f"JWT_SECRET_KEY={val('JWT_SECRET_KEY', 'changeme')}",
        "JWT_ALGORITHM=HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES=30",
    ]


def _server_section(val: _Lookup, *, is_fastapi: bool) -> list[str]:
    """Emit the ``# Server`` block (app config).

    ``LOG_LEVEL`` is always lowercased so FastAPI's ``.lower()`` calls and pino's
    lowercase level labels stay consistent regardless of the source casing.
    """
    lines = ["", "# Server"]
    if is_fastapi:
        lines.append("ENVIRONMENT=development")
        lines.append("DEBUG=True")
        lines.append("PORT=8000")
    else:
        lines.append("NODE_ENV=development")
        lines.append("PORT=8000")
    lines.append(f"LOG_LEVEL={val('LOG_LEVEL', 'info').lower()}")
    lines.append(f"CORS_ORIGINS={val('CORS_ORIGINS', 'http://localhost:4200')}")
    return lines


def _redis_section(val: _Lookup) -> list[str]:
    """Emit the ``# Redis`` block (app config, NestJS/BullMQ only)."""
    return [
        "",
        "# Redis",
        f"REDIS_HOST={val('REDIS_HOST', 'localhost')}",
        f"REDIS_PORT={val('REDIS_PORT', '6379')}",
    ]


def _topology_section(val: _Lookup, *, is_supabase: bool, frontend: bool) -> list[str]:
    """Emit the compose-topology block (read by docker-compose, not the app).

    Compose consumes these as ``${VAR:-default}``; an unset var falls back to
    the same fixed port used before the vars existed, so behaviour is unchanged
    when the section is absent. Every published host port is parametrized here:
    a fixed one would make two scaffolded projects collide on `docker compose up`.
    ``DB_HOST_PORT``/``ADMINER_HOST_PORT`` are omitted for supabase variants
    (they have no local ``db``/``adminer`` services).
    """
    lines = [
        "",
        "# Docker Compose topology (host ports; read by docker-compose.yml)",
        f"API_HOST_PORT={val('API_HOST_PORT', '8000')}",
    ]
    if frontend:
        lines.append(f"FRONTEND_HOST_PORT={val('FRONTEND_HOST_PORT', '4200')}")
    if not is_supabase:
        lines.append(f"DB_HOST_PORT={val('DB_HOST_PORT', '5433')}")
        lines.append(f"ADMINER_HOST_PORT={val('ADMINER_HOST_PORT', '8080')}")
    return lines


def _llm_section(val: _Lookup) -> list[str]:
    """Emit the Azure OpenAI + alternative-provider blocks (BAML, all variants)."""
    return [
        "",
        "# Azure OpenAI (BAML)",
        f"AZURE_OPENAI_BASE_URL={val('AZURE_OPENAI_BASE_URL')}",
        f"AZURE_OPENAI_API_VERSION={val('AZURE_OPENAI_API_VERSION')}",
        f"AZURE_OPENAI_API_KEY={val('AZURE_OPENAI_API_KEY')}",
        "",
        "# Alternative LLM Providers (BAML)",
        f"ANTHROPIC_API_KEY={val('ANTHROPIC_API_KEY')}",
        f"OPENAI_API_KEY={val('OPENAI_API_KEY')}",
        f"GOOGLE_API_KEY={val('GOOGLE_API_KEY')}",
        f"OLLAMA_BASE_URL={val('OLLAMA_BASE_URL', 'http://localhost:11434/v1')}",
    ]


def generate_env(
    framework: str,
    auth: str | None,
    source_env: dict[str, str] | None = None,
    *,
    use_placeholders: bool = False,
    dest: str | None = None,
    frontend: bool = True,
) -> str:
    """Build a .env string for a given framework + auth combination.

    Args:
        framework: "fastapi" or "nestjs"
        auth: None, "token", "supabase", or "entra"
        source_env: parsed root .env dict; defaults to env_defaults.env when None
        use_placeholders: accepted for call-site compatibility; has no effect
            (placeholder values double as working dev defaults in all modes)
        dest: optional file path; when supplied the result is also written there
        frontend: emit the ``FRONTEND_HOST_PORT`` topology var (scope includes
            a frontend). Set False for a backend-only (``api``) scope.

    Declarative section assembly — exempt from the <10-line rule.
    """
    if source_env is None:
        source_env = parse_env(_DEFAULTS_PATH)

    is_supabase = auth == "supabase"
    is_token = auth == "token"
    is_entra = auth == "entra"
    is_fastapi = framework == "fastapi"

    def val(key: str, fallback: str = "") -> str:
        return source_env.get(key, fallback)

    lines: list[str] = []
    lines += _database_section(val, is_fastapi=is_fastapi, is_supabase=is_supabase)
    if is_supabase:
        lines += _supabase_section(val)
    if is_entra:
        lines += _entra_section(val)
    if is_token:
        lines += _token_section(val)
    lines += _server_section(val, is_fastapi=is_fastapi)
    if not is_fastapi:
        lines += _redis_section(val)
    lines += _topology_section(val, is_supabase=is_supabase, frontend=frontend)
    lines += _llm_section(val)

    lines.append("")
    result = "\n".join(lines)
    if dest is not None:
        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(result, encoding="utf-8")
    return result


def generate_env_file(
    framework: str,
    auth: str | None,
    source_env_path: Path,
    dest_env_path: Path,
) -> None:
    """Read the root .env and write a variant-specific .env to dest."""
    source = parse_env(source_env_path)
    content = generate_env(framework, auth, source)
    dest_env_path.parent.mkdir(parents=True, exist_ok=True)
    dest_env_path.write_text(content, encoding="utf-8")


# --- CLI entry point for tasks.json ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("framework", choices=("fastapi", "nestjs"))
    parser.add_argument("--auth", choices=("token", "supabase", "entra"), default=None)
    parser.add_argument("--source", default=".env", help="Path to root .env")
    parser.add_argument("--dest", required=True, help="Path to write output .env")
    args = parser.parse_args()

    generate_env_file(args.framework, args.auth, Path(args.source), Path(args.dest))
    print(f"  Generated: {args.dest}")
