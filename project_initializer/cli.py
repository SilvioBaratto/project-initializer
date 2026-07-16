"""CLI entry point for project-initializer.

The user-facing CLI is a Typer single-command app (:func:`main`) that runs an
interactive questionary wizard (:mod:`project_initializer.wizard`) for any option
not supplied as a flag. When stdin is not a TTY, or ``-y/--yes`` is passed, the
wizard is skipped and unset options fall back to their defaults — so CI and the
``.vscode`` tasks stay non-interactive.
"""

import shutil
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from . import __version__
from .env_generator import generate_env, parse_env
from .file_transforms import (
    append_async_requirements,
    filter_compose,
    generate_frontend_compose,
    strip_nginx_proxy_block,
)
from .wizard import WizardResult, run_wizard

console = Console()

# Errors that mean "this terminal cannot host interactive prompts" — the only
# case the wizard should fall back to non-interactive defaults for. questionary
# is built on prompt_toolkit, which raises NoConsoleScreenBufferError on a
# console it cannot drive (Git Bash / mintty on Windows). EOFError covers a
# closed/empty stdin. Anything else is a real bug and must NOT be swallowed.
_NO_TERMINAL_EXC: tuple[type[BaseException], ...] = (EOFError,)
try:  # prompt_toolkit is a questionary dependency; guard in case it is absent
    from prompt_toolkit.output.win32 import NoConsoleScreenBufferError

    _NO_TERMINAL_EXC = (EOFError, NoConsoleScreenBufferError)
except Exception:  # pragma: no cover - non-Windows / import shape differences
    pass

_NO_TERMINAL_ERRORS = _NO_TERMINAL_EXC

FRAMEWORKS = ("fastapi", "nestjs")
AUTH_MODES = ("token", "supabase", "entra")
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
            layers.append(
                (get_auth_overlay_dir(auth, framework), frozenset(), _combine(reqs))
            )
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
                (
                    get_auth_overlay_dir(auth, framework),
                    frozenset(),
                    _combine(compose, reqs),
                )
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


def _next_steps_lines(auth: str | None, framework: str) -> list[str]:
    """Return the 'Next steps' guidance lines for the given auth/framework combo.

    Declarative data construction — exempt from the <10-line rule.
    """
    lines = ["  # Edit .env with your real keys (ships with working dev defaults)"]
    if auth == "supabase":
        lines.append(
            "  # Configure SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in .env"
        )
    elif auth == "entra":
        lines.append(
            "  # Configure ENTRA_TENANT_ID, ENTRA_API_CLIENT_ID and ENTRA_SPA_CLIENT_ID in .env"
        )
        lines.append("  # Register a SPA app + an API app in Entra ID (see README)")
    lines.append("  docker-compose up -d")
    if framework == "nestjs":
        lines.append("\n  # NestJS API development:")
        lines.append("  cd api && npm install && npm run start:dev")
    else:
        lines.append("\n  # FastAPI development:")
        lines.append(
            "  cd api && pip install -r requirements.txt && uvicorn app.main:app --reload"
        )
    return lines


def _config_panel(
    dest_dir: Path, framework: str, auth: str | None, scope: str, async_db: bool
) -> Panel:
    """Render the leading configuration summary panel."""
    auth_label = "none (open)" if auth is None else auth
    db_label = "async SQLAlchemy" if async_db else "sync SQLAlchemy"
    body = (
        f"[bold]Project[/bold]    {dest_dir.name}\n"
        f"[bold]Scope[/bold]      {scope}\n"
        f"[bold]Framework[/bold]  {framework}\n"
        f"[bold]Auth[/bold]       {auth_label}"
    )
    if scope != "frontend" and framework == "fastapi":
        body += f"\n[bold]Database[/bold]   {db_label}"
    return Panel(body, title="project-initializer", expand=False, border_style="cyan")


def _summary_tree(dest_dir: Path, created: dict[str, bool]) -> Tree:
    """Build a compact tree: top-level dirs with file counts, then root files."""
    top_counts: Counter[str] = Counter()
    root_files: list[str] = []
    for rel in created:
        head, sep, _ = rel.replace("\\", "/").partition("/")
        if sep:
            top_counts[head] += 1
        else:
            root_files.append(rel)

    tree = Tree(f"[bold]{dest_dir.name}[/bold]")
    for name in sorted(top_counts):
        n = top_counts[name]
        tree.add(f"{name}/  [dim]{n} file{'s' if n != 1 else ''}[/dim]")
    for name in sorted(root_files):
        tree.add(name)
    return tree


def copy_template(
    dest_dir: Path,
    project_name: str | None = None,
    auth: str | None = None,
    framework: str = "fastapi",
    scope: str = "fullstack",
    async_db: bool = False,
    verbose: bool = False,
) -> None:
    """Copy template files to destination directory.

    Renders a leading config panel and a compact tree summary (top-level dirs
    with file counts) instead of a line per file. ``verbose=True`` additionally
    lists every distinct file created.
    """
    skip_patterns = {
        "__pycache__",
        ".pyc",
        "node_modules",
        ".git",
        ".env",
        "*.egg-info",
        "dist",
        "build",
        "test-stubs",
    }

    def should_skip(name: str) -> bool:
        return any(
            name == pattern or name.endswith(pattern.lstrip("*"))
            for pattern in skip_patterns
        )

    # relative-path -> True; a set-like dedup so files overwritten by a later
    # overlay layer are counted once, not once per layer.
    created: dict[str, bool] = {}

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
                created[str(dest_item.relative_to(dest_dir))] = True

    def require_dir(path: Path) -> None:
        if not path.exists():
            console.print(f"[red]Error:[/red] templates directory not found at {path}")
            sys.exit(1)

    console.print(_config_panel(dest_dir, framework, auth, scope, async_db))

    for src, skip, transform in select_layers(scope, framework, auth, async_db):
        require_dir(src)
        copy_tree(src, dest_dir, skip, transform)

    # Generate the root .env + .env.example (single source of truth, only when
    # the api layer is present). Both files are byte-identical: the placeholder
    # values double as working dev defaults so `docker compose up` runs as-is.
    # The root location lets docker-compose (env_file) and every subtree share
    # one file — FastAPI walks up to it (infrastructure/config), NestJS points
    # ConfigModule/Prisma at it.
    if scope in ("fullstack", "api"):
        env_example_path = TEMPLATES_ROOT / "env_defaults.env"
        source = parse_env(env_example_path) if env_example_path.exists() else {}
        env_content = generate_env(
            framework, auth, source, frontend=(scope == "fullstack")
        )
        for filename in (".env", ".env.example"):
            env_path = dest_dir / filename
            env_path.write_text(env_content, encoding="utf-8")
            created[filename] = True

    if scope == "frontend":
        compose_path = dest_dir / "docker-compose.yml"
        compose_path.write_text(generate_frontend_compose(), encoding="utf-8")
        created["docker-compose.yml"] = True

    if verbose:
        for rel in sorted(created):
            console.print(f"  [dim]created[/dim] {rel}")

    console.print(_summary_tree(dest_dir, created))
    console.print(
        f"[green]Done[/green] - created [bold]{len(created)}[/bold] files "
        f"in [bold]{dest_dir.name}[/bold]."
    )
    # Plain prints below (not console.print): tests capture these guidance
    # strings via capsys, and they must stay stable, markup-free text.
    print("\nNext steps:")
    print(f"  cd {dest_dir.name}")
    for line in _next_steps_lines(auth, framework):
        print(line)


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


def _version_callback(value: bool) -> None:
    """Print the version and exit (for the top-level --version option)."""
    if value:
        typer.echo(f"project-initializer {__version__}")
        raise typer.Exit()


def _noninteractive_defaults(
    scope: str | None, framework: str | None, auth: str | None, async_db: bool
) -> WizardResult:
    """Resolve unset options to their defaults without prompting.

    Mirrors the old argparse behaviour: scope -> fullstack, framework -> fastapi,
    auth -> None (no auth), async_db -> False.
    """
    return WizardResult(
        scope=scope if scope is not None else "fullstack",
        framework=framework if framework is not None else "fastapi",
        auth=auth,
        async_db=async_db,
    )


def _resolve_choices(
    scope: str | None,
    framework: str | None,
    auth: str | None,
    auth_given: bool,
    async_db: bool,
    async_db_given: bool,
    *,
    interactive: bool,
) -> WizardResult:
    """Turn the raw CLI options into a resolved WizardResult.

    Interactive (a TTY, no ``--yes``): prompt for anything not passed as a flag.
    Non-interactive (piped stdin / ``--yes`` / fully-flagged): apply defaults for
    unset options without prompting, so CI and the .vscode tasks never block.

    Graceful degradation: if the wizard cannot run because the terminal cannot
    host interactive prompts — no console screen buffer (Git Bash / mintty on
    Windows), closed stdin, EOF — fall back to the non-interactive defaults
    rather than crash. ``isatty()`` is not a reliable non-interactivity signal
    on Windows (``NUL`` reports as a console), so this catch is the real guard.

    The fallback is scoped to *terminal-hosting* failures only. A user cancel
    (Ctrl-C -> ``SystemExit``) is re-raised, and any other error (a genuine bug
    in the wizard) propagates instead of being silently masked as a fallback —
    otherwise a broken prompt would look like "the user chose all defaults".
    """
    if not interactive:
        return _noninteractive_defaults(scope, framework, auth, async_db)
    try:
        return run_wizard(
            scope=scope,
            framework=framework,
            auth=auth,
            auth_given=auth_given,
            async_db=async_db,
            async_db_given=async_db_given,
        )
    except _NO_TERMINAL_ERRORS:
        # The terminal can't host prompts (unhostable console / closed stdin /
        # EOF). Fall back to non-interactive defaults rather than crash.
        return _noninteractive_defaults(scope, framework, auth, async_db)


app = typer.Typer(
    add_completion=False,
    help="Initialize a full-stack project with FastAPI or NestJS, Angular, and Docker.",
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command()
def _scaffold(  # noqa: PLR0913 — flat flag surface mirrors the scaffold options
    project_name: str = typer.Argument(
        ".", help="Project directory to create (default: current directory)."
    ),
    version: bool = typer.Option(  # noqa: ARG001 — consumed by the eager callback
        False,
        "-v",
        "--version",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    force: bool = typer.Option(
        False, "-f", "--force", help="Overwrite existing files without prompting."
    ),
    yes: bool = typer.Option(
        False,
        "-y",
        "--yes",
        help="Non-interactive: skip prompts and use defaults for unset options.",
    ),
    scope: str = typer.Option(
        None,
        "--scope",
        help="Layers to scaffold: 'fullstack' (default), 'api', or 'frontend'. "
        "Given -> skips the prompt.",
    ),
    framework: str = typer.Option(
        None,
        "--framework",
        help="Backend framework: 'fastapi' (default) or 'nestjs'. Given -> skips the prompt.",
    ),
    fastapi: bool = typer.Option(
        False, "--fastapi", help="Shorthand for --framework fastapi."
    ),
    nestjs: bool = typer.Option(
        False, "--nestjs", help="Shorthand for --framework nestjs."
    ),
    auth: str = typer.Option(
        None,
        "--auth",
        help="Auth mode: 'token', 'supabase', or 'entra'. Given -> skips the prompt.",
    ),
    async_db: bool = typer.Option(
        False,
        "--async-db",
        help="Add the opt-in async SQLAlchemy path (FastAPI only).",
    ),
    verbose: bool = typer.Option(
        False,
        "-V",
        "--verbose",
        help="List every file created (in addition to the summary tree).",
    ),
) -> None:
    """Scaffold a new project, prompting for any options not supplied as flags."""
    # --fastapi/--nestjs are shorthands for --framework; reject conflicts.
    if fastapi and nestjs:
        raise typer.BadParameter("--fastapi and --nestjs are mutually exclusive.")
    if (fastapi or nestjs) and framework is not None:
        raise typer.BadParameter("--framework cannot be combined with --fastapi/--nestjs.")
    if fastapi:
        framework = "fastapi"
    elif nestjs:
        framework = "nestjs"

    if scope is not None and scope not in SCOPES:
        raise typer.BadParameter(f"'{scope}' is not one of {SCOPES}.", param_hint="--scope")
    if framework is not None and framework not in FRAMEWORKS:
        raise typer.BadParameter(
            f"'{framework}' is not one of {FRAMEWORKS}.", param_hint="--framework"
        )
    if auth is not None and auth not in AUTH_MODES:
        raise typer.BadParameter(f"'{auth}' is not one of {AUTH_MODES}.", param_hint="--auth")

    # Validate the explicitly-supplied flags BEFORE any prompt so an illegal
    # combination fails fast with the exit-code-2 usage error (BadParameter),
    # never reaching the wizard.
    errors = validate_scope(scope, framework, auth, async_db)
    if errors:
        raise typer.BadParameter(errors[0])

    interactive = sys.stdin.isatty() and not yes
    choices = _resolve_choices(
        scope,
        framework,
        auth,
        auth_given=auth is not None,
        async_db=async_db,
        async_db_given=async_db,
        interactive=interactive,
    )
    # No second validation here: validate_scope() treats a non-None framework as
    # an *explicit* flag, but the resolver always fills a concrete framework
    # (e.g. "fastapi" for a frontend scope), so re-validating resolved values
    # would wrongly reject legal combos. The explicit-flag check above already
    # covers the CLI, and the wizard never offers an illegal combination.

    dest_dir = Path.cwd() if project_name == "." else Path.cwd() / project_name

    if dest_dir.exists() and any(dest_dir.iterdir()) and not force:
        response = input(f"Directory '{dest_dir}' is not empty. Continue? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            raise typer.Exit()

    copy_template(
        dest_dir,
        project_name,
        auth=choices.auth,
        framework=choices.framework,
        scope=choices.scope,
        async_db=choices.async_db,
        verbose=verbose,
    )


def main() -> None:
    """Console-script entry point — runs the Typer app over argv."""
    app()


if __name__ == "__main__":
    main()
