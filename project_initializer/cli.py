"""CLI entry point for project-initializer."""

import argparse
import shutil
import sys
from pathlib import Path

from . import __version__


def get_templates_dir() -> Path:
    """Get the path to the templates directory."""
    return Path(__file__).parent / "templates"


def get_auth_templates_dir() -> Path:
    """Get the path to the auth overlay templates directory."""
    return Path(__file__).parent / "templates-auth"


def copy_template(dest_dir: Path, project_name: str | None = None, auth: bool = False) -> None:
    """Copy template files to destination directory."""
    templates_dir = get_templates_dir()

    if not templates_dir.exists():
        print(f"Error: Templates directory not found at {templates_dir}")
        sys.exit(1)

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
        """Recursively copy directory tree."""
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
    print("-" * 40)

    copy_tree(templates_dir, dest_dir)

    if auth:
        auth_templates_dir = get_auth_templates_dir()
        if not auth_templates_dir.exists():
            print(f"Error: Auth templates directory not found at {auth_templates_dir}")
            sys.exit(1)
        print("  Applying auth overlay...")
        copy_tree(auth_templates_dir, dest_dir)

    print("-" * 40)
    print(f"Project created successfully!")
    print(f"\nNext steps:")
    print(f"  cd {dest_dir.name}")
    if auth:
        print(f"  # Auth is enabled — set AUTH_TOKEN in api/.env")
    print(f"  docker-compose up -d")


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="project-initializer",
        description="Initialize a new full-stack project with FastAPI, Angular, and Docker",
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

    copy_template(dest_dir, args.project_name, auth=args.auth)


if __name__ == "__main__":
    main()
