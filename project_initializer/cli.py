"""CLI entry point for project-initializer."""

import argparse
import shutil
import sys
from pathlib import Path

from . import __version__
from .env_generator import generate_env, parse_env

FRAMEWORKS = ("fastapi", "nestjs")
AUTH_MODES = ("token", "supabase")

TEMPLATES_ROOT = Path(__file__).parent


def get_templates_dir() -> Path:
    return TEMPLATES_ROOT / "templates"


def get_api_templates_dir(framework: str) -> Path:
    return TEMPLATES_ROOT / f"templates-api-{framework}"


def get_auth_overlay_dir(auth_mode: str, framework: str) -> Path:
    return TEMPLATES_ROOT / f"templates-{auth_mode}-{framework}"


def get_auth_frontend_overlay_dir(auth_mode: str) -> Path:
    return TEMPLATES_ROOT / f"templates-{auth_mode}-frontend"


def copy_template(
    dest_dir: Path,
    project_name: str | None = None,
    auth: str | None = None,
    framework: str = "fastapi",
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

    def copy_tree(src: Path, dst: Path) -> None:
        """Recursively copy directory tree, merging into existing dirs."""
        dst.mkdir(parents=True, exist_ok=True)

        for item in src.iterdir():
            if should_skip(item.name):
                continue

            dest_item = dst / item.name

            if item.is_dir():
                copy_tree(item, dest_item)
            else:
                shutil.copy2(item, dest_item)
                print(f"  Created: {dest_item.relative_to(dest_dir)}")

    def require_dir(path: Path) -> None:
        if not path.exists():
            print(f"Error: Templates directory not found at {path}")
            sys.exit(1)

    auth_label = f" + {auth} auth" if auth else ""
    print(f"Creating project in: {dest_dir}")
    print(f"Framework: {framework}{auth_label}")
    print("-" * 40)

    # Layer 1: Shared base (frontend, root configs)
    templates_dir = get_templates_dir()
    require_dir(templates_dir)
    copy_tree(templates_dir, dest_dir)

    # Layer 2: Framework-specific API + docker-compose + nginx.conf
    api_templates_dir = get_api_templates_dir(framework)
    require_dir(api_templates_dir)
    copy_tree(api_templates_dir, dest_dir)

    # Layer 3: Auth overlay (token or supabase)
    if auth:
        auth_api_dir = get_auth_overlay_dir(auth, framework)
        require_dir(auth_api_dir)
        print(f"  Applying {auth} auth API overlay...")
        copy_tree(auth_api_dir, dest_dir)

        auth_frontend_dir = get_auth_frontend_overlay_dir(auth)
        require_dir(auth_frontend_dir)
        print(f"  Applying {auth} auth frontend overlay...")
        copy_tree(auth_frontend_dir, dest_dir)

    # Generate .env for the API
    env_example_path = TEMPLATES_ROOT / "env_defaults.env"
    source = parse_env(env_example_path) if env_example_path.exists() else {}
    env_content = generate_env(framework, auth, source, use_placeholders=True)
    api_env_path = dest_dir / "api" / ".env"
    api_env_path.write_text(env_content, encoding="utf-8")
    print(f"  Created: {api_env_path.relative_to(dest_dir)}")

    print("-" * 40)
    print("Project created successfully!")
    print(f"\nNext steps:")
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
        print("  cd api && pip install -r requirements.txt && uvicorn app.main:app --reload")


def main() -> None:
    """Main entry point for the CLI."""
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
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-f", "--force",
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
    parser.set_defaults(framework="fastapi")

    args = parser.parse_args()

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

    copy_template(dest_dir, args.project_name, auth=args.auth, framework=args.framework)


if __name__ == "__main__":
    main()
