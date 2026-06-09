"""CLI entry point for project-initializer."""

import argparse
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from . import __version__
from .env_generator import generate_env, parse_env
from .file_transforms import (
    append_async_requirements,
    filter_compose,
    generate_frontend_compose,
    strip_nginx_proxy_block,
)

FRAMEWORKS = ("fastapi", "nestjs")
AUTH_MODES = ("token", "supabase")
SCOPES = ("fullstack", "api", "frontend")

TEMPLATES_ROOT = Path(__file__).parent


def get_templates_dir() -> Path:
    return TEMPLATES_ROOT / "templates"


def get_api_templates_dir(framework: str) -> Path:
    return TEMPLATES_ROOT / f"templates-api-{framework}"


def get_auth_overlay_dir(auth_mode: str, framework: str) -> Path:
    return TEMPLATES_ROOT / f"templates-{auth_mode}-{framework}"


def get_auth_frontend_overlay_dir(auth_mode: str) -> Path:
    return TEMPLATES_ROOT / f"templates-{auth_mode}-frontend"


def get_asyncdb_overlay_dir() -> Path:
    """Opt-in async SQLAlchemy overlay (FastAPI only), merged by --async-db."""
    return TEMPLATES_ROOT / "templates-asyncdb-fastapi"


def _compose_handler(scope: str) -> Callable:
    """File handler that filters docker-compose.yml for the given scope."""

    def handle(path: Path) -> str | None:
        if path.name == "docker-compose.yml":
            return filter_compose(path.read_text(encoding="utf-8"), scope)
        return None

    return handle


def _nginx_handler() -> Callable:
    """File handler that strips the /api/ proxy block from nginx.conf."""

    def handle(path: Path) -> str | None:
        if path.name == "nginx.conf":
            return strip_nginx_proxy_block(path.read_text(encoding="utf-8"))
        return None

    return handle


def _requirements_handler() -> Callable:
    """File handler that appends the async DB deps to api/requirements.txt."""

    def handle(path: Path) -> str | None:
        if path.name == "requirements.txt":
            return append_async_requirements(path.read_text(encoding="utf-8"))
        return None

    return handle


def _combine(*handlers: Callable | None) -> Callable | None:
    """Compose filename handlers into one transform; None if all are None.

    Returning None when nothing applies preserves byte-identical pass-through
    (the default scaffold). Handlers target disjoint filenames, so first
    non-None wins is an unambiguous dispatch.
    """
    active = [handler for handler in handlers if handler is not None]
    if not active:
        return None

    def transform(path: Path) -> str | None:
        for handler in active:
            result = handler(path)
            if result is not None:
                return result
        return None

    return transform


def select_layers(
    scope: str,
    framework: str,
    auth: str | None,
    async_db: bool = False,
) -> list[tuple[Path, frozenset[str], Callable | None]]:
    """Return the ordered merge layers for the requested scope.

    Each tuple is (src_dir, skip_subdirs, file_transform). The frontend branch
    MUST NOT consult ``framework`` — it is scope-only. When ``async_db`` is set
    (FastAPI only), a requirements transform is composed onto the layers that
    carry ``requirements.txt`` (the async overlay ships none), and the async
    overlay is appended last.

    Declarative data construction — exempt from the <10-line rule.
    """
    base = get_templates_dir()
    api = get_api_templates_dir(framework)
    want_async = async_db and framework == "fastapi"
    reqs = _requirements_handler() if want_async else None

    if scope == "fullstack":
        layers: list[tuple[Path, frozenset[str], Callable | None]] = [
            (base, frozenset(), None),
            (api, frozenset(), _combine(reqs)),
        ]
        if auth:
            layers.append((get_auth_overlay_dir(auth, framework), frozenset(), _combine(reqs)))
            layers.append((get_auth_frontend_overlay_dir(auth), frozenset(), None))
        if want_async:
            layers.append((get_asyncdb_overlay_dir(), frozenset(), None))
        return layers

    if scope == "api":
        compose = _compose_handler("api")
        layers = [
            (base, frozenset({"frontend"}), None),
            (api, frozenset({"frontend"}), _combine(compose, reqs)),
        ]
        if auth:
            layers.append(
                (get_auth_overlay_dir(auth, framework), frozenset(), _combine(compose, reqs))
            )
        if want_async:
            layers.append((get_asyncdb_overlay_dir(), frozenset(), None))
        return layers

    # scope == "frontend"
    layers = [(base, frozenset(), _nginx_handler())]
    if auth:
        layers.append((get_auth_frontend_overlay_dir(auth), frozenset(), None))
    return layers


def _copy_file(src: Path, dst: Path, file_transform: Callable | None) -> None:
    """Copy src to dst, optionally transforming text content.

    The transform receives the source Path and returns transformed text for
    files it targets, or None to pass through to shutil.copy2 (binary-safe).
    """
    if file_transform is not None:
        transformed = file_transform(src)
        if transformed is not None:
            dst.write_text(transformed, encoding="utf-8")
            return
    shutil.copy2(src, dst)


def copy_template(
    dest_dir: Path,
    project_name: str | None = None,
    auth: str | None = None,
    framework: str = "fastapi",
    scope: str = "fullstack",
    async_db: bool = False,
) -> None:
    """Copy template files to destination directory."""
    skip_patterns = {
        "__pycache__",
        ".pyc",
        "node_modules",
        ".git",
        ".env",
        "*.egg-info",
        "dist",
        "build",
    }

    def should_skip(name: str) -> bool:
        return any(
            name == pattern or name.endswith(pattern.lstrip("*"))
            for pattern in skip_patterns
        )

    def copy_tree(
        src: Path,
        dst: Path,
        skip_subdirs: frozenset[str] = frozenset(),
        file_transform: Callable | None = None,
    ) -> None:
        """Recursively copy directory tree, merging into existing dirs."""
        dst.mkdir(parents=True, exist_ok=True)

        for item in src.iterdir():
            if should_skip(item.name):
                continue
            if item.is_dir() and item.name in skip_subdirs:
                continue

            dest_item = dst / item.name

            if item.is_dir():
                copy_tree(item, dest_item, frozenset(), file_transform)
            else:
                _copy_file(item, dest_item, file_transform)
                print(f"  Created: {dest_item.relative_to(dest_dir)}")

    def require_dir(path: Path) -> None:
        if not path.exists():
            print(f"Error: Templates directory not found at {path}")
            sys.exit(1)

    auth_label = f" + {auth} auth" if auth else ""
    print(f"Creating project in: {dest_dir}")
    print(f"Framework: {framework}{auth_label}")
    print("-" * 40)

    for src, skip, transform in select_layers(scope, framework, auth, async_db):
        require_dir(src)
        copy_tree(src, dest_dir, skip, transform)

    # Generate .env for the API (only when the api layer is present)
    if scope in ("fullstack", "api"):
        env_example_path = TEMPLATES_ROOT / "env_defaults.env"
        source = parse_env(env_example_path) if env_example_path.exists() else {}
        env_content = generate_env(framework, auth, source, use_placeholders=True)
        api_env_path = dest_dir / "api" / ".env"
        api_env_path.write_text(env_content, encoding="utf-8")
        print(f"  Created: {api_env_path.relative_to(dest_dir)}")

    if scope == "frontend":
        compose_path = dest_dir / "docker-compose.yml"
        compose_path.write_text(generate_frontend_compose(), encoding="utf-8")
        print(f"  Created: {compose_path.relative_to(dest_dir)}")

    print("-" * 40)
    print("Project created successfully!")
    print("\nNext steps:")
    print(f"  cd {dest_dir.name}")
    print("  # Edit api/.env with your real keys")
    if auth == "supabase":
        print("  # Configure SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in api/.env")
    print("  docker-compose up -d")
    if framework == "nestjs":
        print("\n  # NestJS API development:")
        print("  cd api && npm install && npm run start:dev")
    else:
        print("\n  # FastAPI development:")
        print(
            "  cd api && pip install -r requirements.txt && uvicorn app.main:app --reload"
        )


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser.

    Declarative builder: registers all flags in a flat sequence and is
    therefore exempt from the per-method line limit. ``framework`` defaults
    to ``None`` (no ``set_defaults``) so callers can distinguish an explicit
    ``--fastapi``/``--nestjs`` from the absent case; the ``"fastapi"`` default
    is resolved in ``main()`` after parsing.
    """
    parser = argparse.ArgumentParser(
        prog="project-initializer",
        description="Initialize a new full-stack project with FastAPI or NestJS, Angular, and Docker",
    )
    parser.add_argument(
        "project_name",
        nargs="?",
        default=".",
        help="Name of the project directory to create (default: current directory)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing files without prompting",
    )
    parser.add_argument(
        "--auth",
        nargs="?",
        const="token",
        default=None,
        choices=AUTH_MODES,
        help="Auth mode: 'token' (simple token, default) or 'supabase'",
    )
    parser.add_argument(
        "--scope",
        choices=SCOPES,
        default="fullstack",
        help="Layers to scaffold: 'fullstack' (default), 'api', or 'frontend'",
    )
    parser.add_argument(
        "--async-db",
        dest="async_db",
        action="store_true",
        help="Add the opt-in async SQLAlchemy path (FastAPI only)",
    )

    framework_group = parser.add_mutually_exclusive_group()
    framework_group.add_argument(
        "--fastapi",
        action="store_const",
        const="fastapi",
        dest="framework",
        help="Use FastAPI backend (default)",
    )
    framework_group.add_argument(
        "--nestjs",
        action="store_const",
        const="nestjs",
        dest="framework",
        help="Use NestJS backend",
    )

    return parser


def validate_scope(
    scope: str,
    framework: str | None,
    auth: str | None,
    async_db: bool = False,
) -> list[str]:
    """Return error messages for invalid --scope / framework / auth combos.

    Pure function (no I/O); empty list means valid. ``framework``/``auth`` are
    ``None`` when their flags were omitted, so ``--scope frontend`` alone is
    accepted. ``--async-db`` is a FastAPI api concern: rejected for ``--nestjs``
    and for ``--scope frontend``; ``api``/``fullstack`` accept all API options.
    """
    if scope == "frontend" and framework is not None:
        return ["--scope frontend cannot be combined with --fastapi/--nestjs"]
    if scope == "frontend" and auth is not None:
        return ["--scope frontend cannot be combined with --auth"]
    if async_db and framework == "nestjs":
        return ["--async-db is a FastAPI option and cannot be combined with --nestjs"]
    if async_db and scope == "frontend":
        return ["--async-db cannot be combined with --scope frontend"]
    return []


def main() -> None:
    """Main entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()
    errors = validate_scope(args.scope, args.framework, args.auth, args.async_db)
    if errors:
        parser.error(errors[0])
    framework = args.framework if args.framework is not None else "fastapi"

    # Determine destination directory
    if args.project_name == ".":
        dest_dir = Path.cwd()
    else:
        dest_dir = Path.cwd() / args.project_name

    # Check if directory exists and has content
    if dest_dir.exists() and any(dest_dir.iterdir()) and not args.force:
        response = input(f"Directory '{dest_dir}' is not empty. Continue? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    copy_template(
        dest_dir,
        args.project_name,
        auth=args.auth,
        framework=framework,
        scope=args.scope,
        async_db=args.async_db,
    )


if __name__ == "__main__":
    main()
