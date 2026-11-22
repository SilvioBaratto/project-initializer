"""Guards for the opt-in async SQLAlchemy overlay (#20).

The overlay ``templates-asyncdb-fastapi/`` is additive and isolated: its files
must NOT appear in the base FastAPI template, so the default scaffold stays
byte-identical. The overlay's own ``api/tests/unit/test_async_db.py`` exercises
the async engine/session/repo against in-memory aiosqlite; this repo-level test
merges the base API + overlay into a tmp dir and runs that test file in a
subprocess (``--noconftest`` skips the heavy ``app.main`` conftest), so the
async CRUD contract is verified by the repo suite too.
"""

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from project_initializer.file_transforms import append_async_dependencies

_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES = _ROOT / "project_initializer"
BASE_API = _TEMPLATES / "templates-api-fastapi" / "api"
OVERLAY_API = _TEMPLATES / "templates-asyncdb-fastapi" / "api"

DATABASE_ASYNC = "app/infrastructure/database_async.py"
ITEM_ASYNC = "app/infrastructure/repositories/item_async.py"
OVERLAY_TEST = "tests/unit/test_async_db.py"


def test_when_overlay_listed_async_modules_exist():
    """when the overlay is listed, database_async + item_async modules exist.

    Validates project_initializer/templates-asyncdb-fastapi/api/app/infrastructure/database_async.py, project_initializer/templates-asyncdb-fastapi/api/app/infrastructure/repositories/item_async.py and project_initializer/templates-asyncdb-fastapi/api/tests/unit/test_async_db.py.
    """
    assert (OVERLAY_API / DATABASE_ASYNC).is_file()
    assert (OVERLAY_API / ITEM_ASYNC).is_file()
    assert (OVERLAY_API / OVERLAY_TEST).is_file()


def test_when_base_template_inspected_async_modules_are_absent():
    """when the base template is inspected, the async modules are NOT present (isolated).

    Validates project_initializer/templates-api-fastapi/api/app/infrastructure, which must hold neither database_async.py nor repositories/item_async.py.
    """
    assert not (BASE_API / DATABASE_ASYNC).exists()
    assert not (BASE_API / ITEM_ASYNC).exists()


def _merge(dest: Path) -> Path:
    """Copy base API then the async overlay on top, applying the async dependency transform.

    Mirrors the copy_tree merge in cli.py with the _dependencies_handler applied.
    """
    shutil.copytree(BASE_API, dest, dirs_exist_ok=True)
    shutil.copytree(OVERLAY_API, dest, dirs_exist_ok=True)

    pyproject = dest / "pyproject.toml"
    pyproject.write_text(
        append_async_dependencies(pyproject.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    return dest


def _declared_requirements(api: Path) -> list[str]:
    """Runtime and dev pins declared by the merged pyproject.toml.

    Installing the project itself (``pip install .[dev]``) would register a stray
    ``api`` distribution in the interpreter running this suite; the pins are all
    the overlay test needs.
    """
    project = tomllib.loads((api / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    return [*project["dependencies"], *project["optional-dependencies"]["dev"]]


def _run_python_module(api: Path, *module_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", *module_args],
        cwd=api,
        capture_output=True,
        text=True,
    )


def test_when_async_overlay_test_run_async_crud_passes(tmp_path):
    """when the overlay's async test is run on a merged tree, async CRUD passes.

    Validates project_initializer/templates-asyncdb-fastapi/api/tests/unit/test_async_db.py.
    """
    api = _merge(tmp_path / "api")
    # Same environment as the suite: the pins are already present on a prepared
    # machine, so pip only fetches what is missing.
    install_result = _run_python_module(
        api, "pip", "install", *_declared_requirements(api)
    )
    if install_result.returncode != 0:
        raise RuntimeError(f"pip install failed: {install_result.stderr}")
    # The base pytest.ini enforces a coverage gate for the whole suite; one test
    # file cannot reach it.
    result = _run_python_module(
        api, "pytest", OVERLAY_TEST, "--noconftest", "-q", "--no-cov"
    )
    assert result.returncode == 0, result.stdout + result.stderr
