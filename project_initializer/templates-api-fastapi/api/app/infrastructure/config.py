"""Locates the project ``.env`` and loads it into the process environment.

The ``.env`` lives at the project root, one directory above ``api/``, so a plain
``load_dotenv()`` would miss it when the API starts from ``api/``. Walking up
from the working directory resolves the same file wherever the process starts.
In Docker no ``.env`` exists, because compose injects the variables.
"""

import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DOTENV_FILENAME = ".env"

# The walk stops at the project root so the search never escapes into a parent
# repository or the filesystem root and picks up an unrelated .env.
_PROJECT_ROOT_MARKERS = ("docker-compose.yml", ".git")


def _walk_up_for_dotenv(origin: Path) -> Path | None:
    for directory in (origin, *origin.parents):
        candidate = directory / DOTENV_FILENAME
        if candidate.is_file():
            return candidate
        if any((directory / marker).exists() for marker in _PROJECT_ROOT_MARKERS):
            return None
    return None


def locate_project_dotenv(start: Path | None = None) -> Path | None:
    """Find the project ``.env`` by walking up the directory tree.

    Without ``start`` the search runs from the current working directory first
    and then from this module's location, which covers processes launched from
    an unrelated directory.

    Args:
        start: Directory (or file) to search upward from. When given, only this
            origin is searched.

    Returns:
        The path of the first ``.env`` found below a project-root marker, or
        None when there is none; callers then rely on real environment variables.
    """
    origins = (
        (start.resolve(),)
        if start is not None
        else (Path.cwd(), Path(__file__).resolve())
    )
    for origin in origins:
        found = _walk_up_for_dotenv(origin)
        if found is not None:
            return found
    return None


def load_configuration(dot_env_path: Path | None = None) -> None:
    """Copy the project ``.env`` into ``os.environ``, if there is one.

    Variables already present in the environment win over the file, so Docker,
    CI and exported shell values are never overridden. Missing files are not an
    error.

    Args:
        dot_env_path: Explicit file to load, mainly for tests. When None the file
            is located with ``locate_project_dotenv``.
    """
    resolved = locate_project_dotenv() if dot_env_path is None else dot_env_path
    if resolved is None or not resolved.exists():
        return
    load_dotenv(resolved, override=False)
    logger.debug("Loaded configuration from %s", resolved)
