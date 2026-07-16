"""Guards for the opt-in async SQLAlchemy overlay (#20).

The overlay ``templates-asyncdb-fastapi/`` is additive and isolated: its files
must NOT appear in the base FastAPI template, so the default scaffold stays
byte-identical. The overlay's own ``api/tests/unit/test_async_db.py`` exercises
the async engine/session/repo against in-memory aiosqlite; this repo-level test
merges the base API + overlay into a tmp dir and runs that test file in a
subprocess (``--noconftest`` skips the heavy ``app.main``/BAML conftest), so the
async CRUD contract is verified by the repo suite too.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from project_initializer.file_transforms import append_async_requirements

_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES = _ROOT / "project_initializer"
BASE_API = _TEMPLATES / "templates-api-fastapi" / "api"
OVERLAY_API = _TEMPLATES / "templates-asyncdb-fastapi" / "api"

DATABASE_ASYNC = "app/infrastructure/database_async.py"
BASE_ASYNC = "app/infrastructure/repositories/base_async.py"
OVERLAY_TEST = "tests/unit/test_async_db.py"


def test_when_overlay_listed_async_modules_exist():
    """when the overlay is listed, database_async + base_async modules exist."""
    assert (OVERLAY_API / DATABASE_ASYNC).is_file()
    assert (OVERLAY_API / BASE_ASYNC).is_file()
    assert (OVERLAY_API / OVERLAY_TEST).is_file()


def test_when_base_template_inspected_async_modules_are_absent():
    """when the base template is inspected, the async modules are NOT present (isolated)."""
    assert not (BASE_API / DATABASE_ASYNC).exists()
    assert not (BASE_API / BASE_ASYNC).exists()


def _merge(dest: Path) -> Path:
    """Copy base API then the async overlay on top, applying async requirements transform.

    Mirrors the copy_tree merge in cli.py with the _requirements_handler applied.
    """
    shutil.copytree(BASE_API, dest, dirs_exist_ok=True)
    shutil.copytree(OVERLAY_API, dest, dirs_exist_ok=True)

    # Apply the async requirements transformation to the merged requirements.txt
    req_file = dest / "requirements.txt"
    if req_file.exists():
        req_file.write_text(
            append_async_requirements(req_file.read_text(encoding="utf-8")),
            encoding="utf-8",
        )

    return dest


def test_when_async_overlay_test_run_async_crud_passes(tmp_path):
    """when the overlay's async test is run on a merged tree, async CRUD passes."""
    api = _merge(tmp_path / "api")
    # Install dependencies from the merged requirements.txt (which includes asyncpg)
    # Use the current Python's site-packages by running in the same environment
    install_result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        cwd=api,
        capture_output=True,
        text=True,
    )
    if install_result.returncode != 0:
        raise RuntimeError(f"pip install failed: {install_result.stderr}")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", OVERLAY_TEST, "--noconftest", "-q"],
        cwd=api,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
