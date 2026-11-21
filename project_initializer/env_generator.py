"""Generate variant-specific .env files from the root .env.

The generator is composed of small per-section builders (``_database_section``,
``_supabase_section``, ``_entra_section``, ``_token_section``, ``_server_section``,
``_topology_section``). Each returns a
``list[str]`` of ``KEY=VALUE`` / comment lines and is selected by the
framework/auth flags in :func:`generate_env`. Splitting the flat body into
sections keeps every variant's output explicit and testable.

Two kinds of variables are emitted, grouped into commented sub-sections:

* **app config** — read by the running app (``DATABASE_URL``, ``ENTRA_*``, ...).
* **compose topology** — read by ``docker-compose.yml`` to publish host ports
  (``API_HOST_PORT``, ``FRONTEND_HOST_PORT``, ``DB_HOST_PORT``). Compose consumes
  these as ``${VAR:-default}`` so an unset var falls back to today's fixed port.

Non-secret values carry a working dev default so a freshly scaffolded project
runs ``docker compose up`` with no edits. Secrets (:data:`GENERATED_SECRET_KEYS`)
never do: the ``.env`` receives freshly generated random values and the
``.env.example`` leaves them blank, so no usable credential is ever shipped in a
file that gets committed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from secrets import token_urlsafe

# Callable[(key, fallback)] -> str, used by the private section builders.
_Lookup = Callable[..., str]

_DEFAULTS_PATH = Path(__file__).parent / "env_defaults.env"

# Keys whose value is a credential. They are generated per scaffold and are
# blank in every example file: AUTH_TOKEN (token auth, both frameworks) and
# JWT_SECRET_KEY (FastAPI token auth).
GENERATED_SECRET_KEYS: tuple[str, ...] = (
    "AUTH_TOKEN",
    "JWT_SECRET_KEY",
)

# The value earlier releases shipped for AUTH_TOKEN and JWT_SECRET_KEY. It is
# well known, so a generated secret replaces it instead of preserving it.
LEGACY_PLACEHOLDER = "changeme"

# 32 random bytes encode to 43 URL-safe characters, above the strictest minimum
# the templates enforce (32, the NestJS token variant).
_SECRET_ENTROPY_BYTES = 32


def new_generated_secrets() -> dict[str, str]:
    """Create one fresh random value for every key in :data:`GENERATED_SECRET_KEYS`.

    Each value is 43 URL-safe characters (``[A-Za-z0-9_-]``), so it needs no
    quoting in a ``.env`` file and satisfies the length floors of both backends.
    Every key gets its own value; leaking one secret reveals nothing about the
    others.

    Returns:
        A mapping from each generated secret key to its new random value.
    """
    return {key: token_urlsafe(_SECRET_ENTROPY_BYTES) for key in GENERATED_SECRET_KEYS}


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
    The Supabase FastAPI variant also pins TLS on and a 5-minute connection
    recycle, because the pooler drops idle connections.
    """
    lines = ["# Database"]
    if is_supabase:
        if is_fastapi:
            lines.append(f"DATABASE_URL={val('SUPABASE_DATABASE_URL')}")
            lines.append(f"DIRECT_DATABASE_URL={val('SUPABASE_DIRECT_DATABASE_URL')}")
            lines.append("DATABASE_SSL_MODE=require")
            lines.append("DATABASE_POOL_RECYCLE=300")
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


def _token_section(val: _Lookup, *, is_fastapi: bool) -> list[str]:
    """Emit the ``# Authentication`` block (app config, token variants only).

    Only the FastAPI variant has the OAuth2-password JWT flow, so only it gets
    the ``JWT_*`` keys; emitting a signing secret NestJS never reads would just
    be a credential nobody rotates.
    """
    lines = ["", "# Authentication", f"AUTH_TOKEN={val('AUTH_TOKEN')}"]
    if is_fastapi:
        lines += [
            f"JWT_SECRET_KEY={val('JWT_SECRET_KEY')}",
            "JWT_ALGORITHM=HS256",
            "ACCESS_TOKEN_EXPIRE_MINUTES=30",
        ]
    return lines


def _server_section(val: _Lookup, *, is_fastapi: bool) -> list[str]:
    """Emit the ``# Server`` block (app config).

    ``LOG_LEVEL`` is always lowercased so FastAPI's ``.lower()`` calls and pino's
    lowercase level labels stay consistent regardless of the source casing.
    ``DEBUG`` is pinned off: when on, the framework renders tracebacks to
    clients, and FastAPI settings refuse it outside development anyway.
    """
    lines = ["", "# Server"]
    if is_fastapi:
        lines.append("ENVIRONMENT=development")
        lines.append("DEBUG=false")
        lines.append("PORT=8000")
    else:
        lines.append("# development matches the compose dev target (devDependencies installed).")
        lines.append("# The production image sets NODE_ENV=production itself; never hand it this file.")
        lines.append("NODE_ENV=development")
        lines.append("PORT=8000")
    lines.append(f"LOG_LEVEL={val('LOG_LEVEL', 'info').lower()}")
    lines.append(f"CORS_ORIGINS={val('CORS_ORIGINS', 'http://localhost:4200')}")
    return lines


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


def _fill_secret(current: str, generated: str | None) -> str:
    """Pick the value of a secret key: the generated one only replaces a blank or legacy value.

    An explicit value the caller supplied always wins, so re-running the
    generator never overwrites a credential somebody already chose.
    """
    if generated and current in ("", LEGACY_PLACEHOLDER):
        return generated
    return current


def _make_lookup(
    source_env: Mapping[str, str],
    generated: Mapping[str, str],
    *,
    use_placeholders: bool,
) -> _Lookup:
    """Build the ``val(key, fallback)`` lookup the section builders share.

    Plain keys read ``source_env`` with the fallback; keys in
    :data:`GENERATED_SECRET_KEYS` are blank for an example file and otherwise
    filled from ``generated`` only while the source value is blank or legacy.
    """

    def val(key: str, fallback: str = "") -> str:
        value = source_env.get(key, fallback)
        if key not in GENERATED_SECRET_KEYS:
            return value
        if use_placeholders:
            return ""
        return _fill_secret(value, generated.get(key))

    return val


def _assemble_lines(
    framework: str, auth: str | None, val: _Lookup, *, frontend: bool
) -> list[str]:
    """Concatenate the sections that apply to one framework and auth mode."""
    is_supabase = auth == "supabase"
    is_fastapi = framework == "fastapi"
    lines = _database_section(val, is_fastapi=is_fastapi, is_supabase=is_supabase)
    if is_supabase:
        lines += _supabase_section(val)
    if auth == "entra":
        lines += _entra_section(val)
    if auth == "token":
        lines += _token_section(val, is_fastapi=is_fastapi)
    lines += _server_section(val, is_fastapi=is_fastapi)
    lines += _topology_section(val, is_supabase=is_supabase, frontend=frontend)
    return lines


def generate_env(
    framework: str,
    auth: str | None,
    source_env: dict[str, str] | None = None,
    *,
    secrets: Mapping[str, str] | None = None,
    use_placeholders: bool = False,
    dest: str | None = None,
    frontend: bool = True,
) -> str:
    """Build a .env string for a given framework + auth combination.

    Args:
        framework: "fastapi" or "nestjs"
        auth: None, "token", "supabase", or "entra"
        source_env: parsed root .env dict; defaults to env_defaults.env when None
        secrets: values for :data:`GENERATED_SECRET_KEYS`, typically from
            :func:`new_generated_secrets`. A secret fills a key only while the
            source value is empty or :data:`LEGACY_PLACEHOLDER`; any other
            source value is kept. Without ``secrets`` a blank key stays blank,
            which makes the app refuse to start instead of using a guessable
            credential.
        use_placeholders: render an example file: every key in
            :data:`GENERATED_SECRET_KEYS` is emitted blank, whatever the source
            holds, so the file is safe to commit. Mutually exclusive with
            ``secrets``.
        dest: optional file path; when supplied the result is also written there
        frontend: emit the ``FRONTEND_HOST_PORT`` topology var (scope includes
            a frontend). Set False for a backend-only (``api``) scope.

    Returns:
        The rendered file content.

    Raises:
        ValueError: ``secrets`` and ``use_placeholders`` were both given.
    """
    if use_placeholders and secrets:
        raise ValueError("secrets cannot be combined with use_placeholders=True")
    if source_env is None:
        source_env = parse_env(_DEFAULTS_PATH)
    val = _make_lookup(source_env, secrets or {}, use_placeholders=use_placeholders)
    lines = _assemble_lines(framework, auth, val, frontend=frontend)
    lines.append("")
    result = "\n".join(lines)
    if dest is not None:
        _write_text(Path(dest), result)
    return result


def _write_text(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` as UTF-8, creating missing parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_env_file(
    framework: str,
    auth: str | None,
    source_env_path: Path,
    dest_env_path: Path,
) -> None:
    """Read the root .env and write a variant-specific .env to dest.

    Secrets the root .env leaves blank (or still at the legacy placeholder) are
    generated, so the destination always boots; values the root .env sets
    explicitly are copied unchanged.
    """
    source = parse_env(source_env_path)
    content = generate_env(framework, auth, source, secrets=new_generated_secrets())
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
