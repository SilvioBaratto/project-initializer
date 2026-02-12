"""CLI entry point for project-initializer."""

import argparse
import shutil
import sys
from pathlib import Path

from . import __version__

FRAMEWORKS = ("fastapi", "nestjs")


def get_templates_dir() -> Path:
    """Get the path to the shared base templates directory."""
    return Path(__file__).parent / "templates"


def get_api_templates_dir(framework: str) -> Path:
    """Get the path to the framework-specific API templates directory."""
    return Path(__file__).parent / f"templates-api-{framework}"


def get_auth_api_templates_dir(framework: str) -> Path:
    """Get the path to the framework-specific auth API overlay directory."""
    return Path(__file__).parent / f"templates-auth-{framework}"


def get_auth_frontend_templates_dir() -> Path:
    """Get the path to the shared frontend auth overlay directory."""
    return Path(__file__).parent / "templates-auth-frontend"


def copy_template(
    dest_dir: Path,
    project_name: str | None = None,
    auth: bool = False,
    framework: str = "fastapi",
) -> None:
    """Copy template files to destination directory."""
    # Files and directories to skip
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

    print(f"Creating project in: {dest_dir}")
    print(f"Framework: {framework}")
    print("-" * 40)

    # Layer 1: Shared base (frontend, root configs)
    templates_dir = get_templates_dir()
    if not templates_dir.exists():
        print(f"Error: Templates directory not found at {templates_dir}")
        sys.exit(1)
    copy_tree(templates_dir, dest_dir)

    # Layer 2: Framework-specific API + docker-compose + nginx.conf
    api_templates_dir = get_api_templates_dir(framework)
    if not api_templates_dir.exists():
        print(f"Error: API templates directory not found at {api_templates_dir}")
        sys.exit(1)
    copy_tree(api_templates_dir, dest_dir)

    # Layer 3: Auth overlays (if requested)
    if auth:
        auth_api_dir = get_auth_api_templates_dir(framework)
        if not auth_api_dir.exists():
            print(f"Error: Auth API templates not found at {auth_api_dir}")
            sys.exit(1)
        print("  Applying auth API overlay...")
        copy_tree(auth_api_dir, dest_dir)

        auth_frontend_dir = get_auth_frontend_templates_dir()
        if not auth_frontend_dir.exists():
            print(f"Error: Auth frontend templates not found at {auth_frontend_dir}")
            sys.exit(1)
        print("  Applying auth frontend overlay...")
        copy_tree(auth_frontend_dir, dest_dir)

    print("-" * 40)
    print("Project created successfully!")
    print(f"\nNext steps:")
    print(f"  cd {dest_dir.name}")
    if auth:
        print("  # Auth is enabled — set AUTH_TOKEN in api/.env")
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
        action="store_true",
        help="Include authentication scaffolding (login page, guards, auth endpoint)",
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
