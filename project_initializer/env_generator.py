"""Generate variant-specific .env files from the root .env."""

from __future__ import annotations

from pathlib import Path

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


def generate_env(
    framework: str,
    auth: str | None,
    source_env: dict[str, str] | None = None,
    *,
    use_placeholders: bool = False,
    dest: str | None = None,
) -> str:
    """Build a .env string for a given framework + auth combination.

    Args:
        framework: "fastapi" or "nestjs"
        auth: None, "token", "supabase", or "entra"
        source_env: parsed root .env dict; defaults to env_defaults.env when None
        use_placeholders: if True, emit placeholder values for user-facing output
        dest: optional file path; when supplied the result is also written there
    """
    if source_env is None:
        source_env = parse_env(_DEFAULTS_PATH)
    lines: list[str] = []
    is_supabase = auth == "supabase"
    is_token = auth == "token"
    is_entra = auth == "entra"
    is_fastapi = framework == "fastapi"

    def val(key: str, fallback: str = "") -> str:
        return source_env.get(key, fallback)

    # --- Database ---
    lines.append("# Database")
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

    # --- Supabase client ---
    if is_supabase:
        lines.append("")
        lines.append("# Supabase")
        lines.append(f"SUPABASE_URL={val('SUPABASE_URL')}")
        lines.append(f"SUPABASE_PUBLISHABLE_KEY={val('SUPABASE_PUBLISHABLE_KEY')}")

    # --- Microsoft Entra ID ---
    if is_entra:
        lines.append("")
        lines.append("# Microsoft Entra ID")
        lines.append(f"ENTRA_TENANT_ID={val('ENTRA_TENANT_ID')}")
        lines.append(f"ENTRA_API_CLIENT_ID={val('ENTRA_API_CLIENT_ID')}")
        lines.append(f"ENTRA_API_AUDIENCE={val('ENTRA_API_AUDIENCE')}")
        lines.append(f"ENTRA_API_SCOPE={val('ENTRA_API_SCOPE')}")
        lines.append(f"ENTRA_SPA_CLIENT_ID={val('ENTRA_SPA_CLIENT_ID')}")

    # --- Auth ---
    if is_token:
        lines.append("")
        lines.append("# Authentication")
        lines.append(f"AUTH_TOKEN={val('AUTH_TOKEN')}")
        lines.append(f"JWT_SECRET_KEY={val('JWT_SECRET_KEY', 'changeme')}")
        lines.append("JWT_ALGORITHM=HS256")
        lines.append("ACCESS_TOKEN_EXPIRE_MINUTES=30")

    # --- Server ---
    lines.append("")
    lines.append("# Server")
    if is_fastapi:
        lines.append("ENVIRONMENT=development")
        lines.append("DEBUG=True")
        lines.append("PORT=8000")
    else:
        lines.append("NODE_ENV=development")
        lines.append("PORT=8000")
    lines.append(f"LOG_LEVEL={val('LOG_LEVEL', 'info').lower()}")
    lines.append(f"CORS_ORIGINS={val('CORS_ORIGINS', 'http://localhost:4200')}")

    # --- Redis (NestJS BullMQ queue backend) ---
    if not is_fastapi:
        lines.append("")
        lines.append("# Redis")
        lines.append(f"REDIS_HOST={val('REDIS_HOST', 'localhost')}")
        lines.append(f"REDIS_PORT={val('REDIS_PORT', '6379')}")

    # --- Azure OpenAI ---
    lines.append("")
    lines.append("# Azure OpenAI (BAML)")
    lines.append(f"AZURE_OPENAI_BASE_URL={val('AZURE_OPENAI_BASE_URL')}")
    lines.append(f"AZURE_OPENAI_API_VERSION={val('AZURE_OPENAI_API_VERSION')}")
    lines.append(f"AZURE_OPENAI_API_KEY={val('AZURE_OPENAI_API_KEY')}")

    # --- Alternative LLM ---
    lines.append("")
    lines.append("# Alternative LLM Providers (BAML)")
    lines.append(f"ANTHROPIC_API_KEY={val('ANTHROPIC_API_KEY')}")
    lines.append(f"OPENAI_API_KEY={val('OPENAI_API_KEY')}")
    lines.append(f"GOOGLE_API_KEY={val('GOOGLE_API_KEY')}")
    lines.append(
        f"OLLAMA_BASE_URL={val('OLLAMA_BASE_URL', 'http://localhost:11434/v1')}"
    )

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
