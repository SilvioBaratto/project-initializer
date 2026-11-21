"""Where the FastAPI Entra guarantees live in the templates.

The Entra overlay used to hold everything in one ``api/deps.py``. Its token
verification now lives in ``infrastructure/auth/entra.py``, its settings in
``infrastructure/auth_settings.py``, the auth seam in ``api/auth_deps.py``, and the
status code of each domain error in the base ``api/handlers.py``. The source-text
tests of the Entra guarantees read the files through these helpers, so a move
touches one place.
"""

from pathlib import Path

from project_initializer.env_generator import generate_env

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "project_initializer"
ENTRA_API_DIR = PACKAGE_DIR / "templates-entra-fastapi" / "api"
BASE_API_DIR = PACKAGE_DIR / "templates-api-fastapi" / "api"

ENTRA_VERIFIER_PATH = ENTRA_API_DIR / "app" / "infrastructure" / "auth" / "entra.py"
ENTRA_AUTH_SETTINGS_PATH = ENTRA_API_DIR / "app" / "infrastructure" / "auth_settings.py"
ENTRA_AUTH_DEPS_PATH = ENTRA_API_DIR / "app" / "api" / "auth_deps.py"
BASE_HANDLERS_PATH = BASE_API_DIR / "app" / "api" / "handlers.py"


def entra_verifier_text() -> str:
    """Return the source of the in-process Entra token verifier."""
    return ENTRA_VERIFIER_PATH.read_text(encoding="utf-8")


def entra_auth_settings_text() -> str:
    """Return the source of the Entra settings overlay."""
    return ENTRA_AUTH_SETTINGS_PATH.read_text(encoding="utf-8")


def entra_auth_deps_text() -> str:
    """Return the source of the Entra auth seam (``get_current_user`` and friends)."""
    return ENTRA_AUTH_DEPS_PATH.read_text(encoding="utf-8")


def base_handlers_text() -> str:
    """Return the source of the base exception handlers, where domain errors get a status."""
    return BASE_HANDLERS_PATH.read_text(encoding="utf-8")


def generated_entra_env_example() -> str:
    """Render the ``.env.example`` the CLI writes for a FastAPI Entra scaffold.

    The overlay ships no ``.env.example`` of its own any more: the CLI renders it
    from ``env_generator`` with every secret blank.

    Returns:
        The file content.
    """
    return generate_env("fastapi", "entra", use_placeholders=True)


def auth_failure_statuses_are_wired() -> tuple[bool, bool]:
    """Tell whether the 401 and 403 answers are wired from the verifier to the handlers.

    Returns:
        ``(unauthorized, forbidden)``. Each is True when the verifier raises the
        matching domain error and ``handlers.py`` answers that error with the
        matching status.
    """
    verifier = entra_verifier_text()
    handlers = base_handlers_text()
    unauthorized = (
        "AuthenticationError" in verifier and "HTTP_401_UNAUTHORIZED" in handlers
    )
    forbidden = "AuthorizationError" in verifier and "HTTP_403_FORBIDDEN" in handlers
    return unauthorized, forbidden
