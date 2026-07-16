"""Interactive prompt layer for the project-initializer CLI.

Collects the scaffold choices (scope, framework, auth mode, async DB) via
questionary single-select menus and returns a plain :class:`WizardResult` the
CLI bridges into the ``copy_template()`` flow.

Each prompt is skipped when the caller already supplied the corresponding flag,
so a fully-flagged invocation runs with zero prompts (used by CI and by the
``.vscode`` tasks). Framework / auth / async-db prompts are also skipped for a
frontend-only scope — those are API concerns and ``validate_scope`` rejects
them there, so the wizard never offers an illegal combination.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import questionary

FRAMEWORKS = ("fastapi", "nestjs")
AUTH_MODES = ("none", "token", "supabase", "entra")

SCOPE_FULLSTACK = "fullstack"
SCOPE_API = "api"
SCOPE_FRONTEND = "frontend"
SCOPES = (SCOPE_FULLSTACK, SCOPE_API, SCOPE_FRONTEND)


@dataclass
class WizardResult:
    """Answers collected from the wizard, ready for the scaffold flow.

    Mirrors the (scope, framework, auth, async_db) inputs that
    ``copy_template()`` consumes. ``auth`` is ``None`` for the no-auth case
    (the wizard maps the "none" menu choice to ``None``).
    """

    scope: str
    framework: str
    auth: str | None
    async_db: bool


def scope_includes_api(scope: str) -> bool:
    return scope in (SCOPE_FULLSTACK, SCOPE_API)


def _abort_if_cancelled(value: object) -> object:
    """Exit cleanly if the user cancelled a prompt (Ctrl-C returns None)."""
    if value is None:
        print("Aborted.")
        sys.exit(0)
    return value


def _prompt_scope() -> str:
    """Ask which project scope to scaffold (fullstack / api / frontend)."""
    answer = questionary.select(
        "Scope",
        choices=[
            questionary.Choice(title="fullstack (api + frontend)", value=SCOPE_FULLSTACK),
            questionary.Choice(title="api (backend only)", value=SCOPE_API),
            questionary.Choice(title="frontend (Angular only)", value=SCOPE_FRONTEND),
        ],
        default=SCOPE_FULLSTACK,
    ).ask()
    return str(_abort_if_cancelled(answer))


def _prompt_framework() -> str:
    """Ask for the backend framework (single-select fastapi/nestjs)."""
    answer = questionary.select(
        "Framework",
        choices=[
            questionary.Choice(title="FastAPI (Python)", value="fastapi"),
            questionary.Choice(title="NestJS (TypeScript)", value="nestjs"),
        ],
        default="fastapi",
    ).ask()
    return str(_abort_if_cancelled(answer))


def _prompt_auth() -> str | None:
    """Ask for the auth mode; maps the "none" choice to ``None``."""
    answer = questionary.select(
        "Auth",
        choices=[
            questionary.Choice(title="none (open)", value="none"),
            questionary.Choice(title="token (bearer / JWT)", value="token"),
            questionary.Choice(title="supabase (JWT + hosted DB)", value="supabase"),
            questionary.Choice(title="entra (Microsoft Entra ID)", value="entra"),
        ],
        default="none",
    ).ask()
    resolved = str(_abort_if_cancelled(answer))
    return None if resolved == "none" else resolved


def _prompt_async_db() -> bool:
    """Ask whether to add the opt-in async SQLAlchemy path (FastAPI only).

    No ``default=`` is passed: questionary matches ``default`` against a choice
    *value* (here booleans), not the title, and the first choice ("No") is the
    default anyway — which is the intended sync-by-default behaviour.
    """
    answer = questionary.select(
        "Async database (FastAPI async SQLAlchemy path)",
        choices=[
            questionary.Choice(title="No (sync SQLAlchemy)", value=False),
            questionary.Choice(title="Yes (async SQLAlchemy)", value=True),
        ],
    ).ask()
    return bool(_abort_if_cancelled(answer))


def run_wizard(
    *,
    scope: str | None = None,
    framework: str | None = None,
    auth: str | None = None,
    auth_given: bool = False,
    async_db: bool = False,
    async_db_given: bool = False,
) -> WizardResult:
    """Run the wizard, prompting only for values not already supplied.

    Any argument passed as a concrete value skips its menu, so a fully-specified
    call performs no prompts. Framework / auth / async-db prompts are skipped
    entirely for a frontend-only scope (they are API concerns).

    ``auth_given`` / ``async_db_given`` disambiguate an explicit ``--auth none``
    / ``--async-db``-absent from "not supplied": ``auth`` is ``None`` both when
    the user chose none and when the flag was omitted, and ``async_db`` is a
    plain bool, so the caller passes these companion flags to say whether the
    value was set on the command line.
    """
    resolved_scope = scope if scope is not None else _prompt_scope()

    # A frontend-only scaffold has no backend: force the API dimensions off and
    # skip their menus. validate_scope() also rejects them, so this keeps the
    # wizard from ever offering an illegal combination.
    if not scope_includes_api(resolved_scope):
        return WizardResult(
            scope=resolved_scope, framework="fastapi", auth=None, async_db=False
        )

    resolved_framework = framework if framework is not None else _prompt_framework()
    resolved_auth = auth if auth_given else _prompt_auth()

    # Async DB is a FastAPI-only concern; never prompt for it under NestJS.
    if resolved_framework == "nestjs":
        resolved_async = False
    elif async_db_given:
        resolved_async = async_db
    else:
        resolved_async = _prompt_async_db()

    return WizardResult(
        scope=resolved_scope,
        framework=resolved_framework,
        auth=resolved_auth,
        async_db=resolved_async,
    )
