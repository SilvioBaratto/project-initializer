"""Unit tests for locating and loading the project ``.env``."""

import os
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

import app.main as application_entry_point
from app.infrastructure import config
from app.infrastructure.config import DOTENV_FILENAME, locate_project_dotenv

pytestmark = pytest.mark.unit

PROBE_VARIABLE = "TEST_CONFIG_PROBE_VALUE"
FILE_VALUE = "from-the-dotenv-file"
EXPORTED_VALUE = "exported-by-the-shell"
ROOT_MARKERS = ["docker-compose.yml", ".git"]


@pytest.fixture
def isolated_environment() -> Iterator[None]:
    """Undo every change a test makes to ``os.environ``, including ``load_dotenv``."""
    with mock.patch.dict(os.environ):
        yield


def make_project(tmp_path: Path, marker: str = "docker-compose.yml") -> Path:
    """Create ``project/`` holding a root marker and ``api/app/`` below it."""
    project = tmp_path / "project"
    (project / "api" / "app").mkdir(parents=True)
    (project / marker).touch()
    return project


def write_dotenv(directory: Path, body: str = "") -> Path:
    """Write a ``.env`` file in ``directory`` and return its path."""
    dotenv = directory / DOTENV_FILENAME
    dotenv.write_text(body, encoding="utf-8")
    return dotenv


def test_when_dotenv_is_in_the_start_directory_then_it_is_found(tmp_path):
    """when the start directory holds a .env, that file is returned.

    Validates app.infrastructure.config.locate_project_dotenv().
    """
    project = make_project(tmp_path)
    dotenv = write_dotenv(project / "api")

    assert locate_project_dotenv(project / "api") == dotenv


def test_when_dotenv_is_in_a_parent_directory_then_the_walk_finds_it(tmp_path):
    """when only an ancestor holds a .env, the upward walk reaches it.

    Validates app.infrastructure.config.locate_project_dotenv().
    """
    project = make_project(tmp_path)
    dotenv = write_dotenv(project)

    assert locate_project_dotenv(project / "api" / "app") == dotenv


@pytest.mark.parametrize("marker", ROOT_MARKERS)
def test_when_dotenv_sits_beside_the_root_marker_then_it_is_found(tmp_path, marker):
    """when the .env shares a directory with the project-root marker, it is returned.

    Validates app.infrastructure.config.locate_project_dotenv().
    """
    project = make_project(tmp_path, marker)
    dotenv = write_dotenv(project)

    assert locate_project_dotenv(project / "api") == dotenv


@pytest.mark.parametrize("marker", ROOT_MARKERS)
def test_when_the_root_marker_is_reached_then_a_dotenv_above_it_is_ignored(
    tmp_path, marker
):
    """when no .env exists up to the project root, an unrelated one above is not used.

    Validates app.infrastructure.config.locate_project_dotenv().
    """
    write_dotenv(tmp_path)
    project = make_project(tmp_path, marker)

    assert locate_project_dotenv(project / "api") is None


def test_when_start_is_a_file_then_the_search_runs_from_its_directory(tmp_path):
    """when the start path is a file, the search covers its directory and ancestors.

    Validates app.infrastructure.config.locate_project_dotenv().
    """
    project = make_project(tmp_path)
    dotenv = write_dotenv(project)
    module = project / "api" / "app" / "settings.py"
    module.touch()

    assert locate_project_dotenv(module) == dotenv


def test_when_no_start_is_given_then_the_search_begins_at_the_working_directory(
    tmp_path, monkeypatch
):
    """when no start is given, the current working directory is searched first.

    Validates app.infrastructure.config.locate_project_dotenv().
    """
    project = make_project(tmp_path)
    dotenv = write_dotenv(project)
    monkeypatch.chdir(project / "api")

    assert locate_project_dotenv() == dotenv


def test_when_the_working_directory_has_no_dotenv_then_the_module_location_is_searched(
    tmp_path, monkeypatch
):
    """when the process starts elsewhere, the search falls back to the module location.

    Validates app.infrastructure.config.locate_project_dotenv().
    """
    project = make_project(tmp_path)
    dotenv = write_dotenv(project)
    unrelated = tmp_path / "elsewhere"
    unrelated.mkdir()
    (unrelated / ".git").touch()
    monkeypatch.chdir(unrelated)
    module_location = project / "api" / "app" / "infrastructure" / "config.py"
    monkeypatch.setattr(config, "__file__", str(module_location))

    assert locate_project_dotenv() == dotenv


def test_when_the_file_defines_a_variable_then_load_configuration_exports_it(
    tmp_path, isolated_environment
):
    """when the variable is not yet exported, the file's value is loaded.

    Validates app.infrastructure.config.load_configuration().
    """
    dotenv = write_dotenv(tmp_path, f"{PROBE_VARIABLE}={FILE_VALUE}\n")
    os.environ.pop(PROBE_VARIABLE, None)

    config.load_configuration(dotenv)

    assert os.environ[PROBE_VARIABLE] == FILE_VALUE


def test_when_the_variable_is_already_exported_then_the_file_does_not_override_it(
    tmp_path, isolated_environment
):
    """when the environment already defines the variable, Docker or CI values win.

    Validates app.infrastructure.config.load_configuration().
    """
    dotenv = write_dotenv(tmp_path, f"{PROBE_VARIABLE}={FILE_VALUE}\n")
    os.environ[PROBE_VARIABLE] = EXPORTED_VALUE

    config.load_configuration(dotenv)

    assert os.environ[PROBE_VARIABLE] == EXPORTED_VALUE


def test_when_the_explicit_file_is_missing_then_the_environment_is_left_alone(
    tmp_path, isolated_environment
):
    """when the given path does not exist, nothing is loaded and nothing fails.

    Validates app.infrastructure.config.load_configuration().
    """
    os.environ.pop(PROBE_VARIABLE, None)
    before = dict(os.environ)

    config.load_configuration(tmp_path / "absent" / DOTENV_FILENAME)

    assert dict(os.environ) == before


def test_when_no_path_is_given_then_the_located_file_is_loaded(
    tmp_path, monkeypatch, isolated_environment
):
    """when no path is given, the file found by the upward walk is the one loaded.

    Validates app.infrastructure.config.load_configuration().
    """
    dotenv = write_dotenv(tmp_path, f"{PROBE_VARIABLE}={FILE_VALUE}\n")
    os.environ.pop(PROBE_VARIABLE, None)
    monkeypatch.setattr(config, "locate_project_dotenv", lambda: dotenv)

    config.load_configuration()

    assert os.environ[PROBE_VARIABLE] == FILE_VALUE


def test_when_no_dotenv_can_be_located_then_load_configuration_does_nothing(
    monkeypatch, isolated_environment
):
    """when the walk finds no file, as in Docker, loading is a silent no-op.

    Validates app.infrastructure.config.load_configuration().
    """
    before = dict(os.environ)
    monkeypatch.setattr(config, "locate_project_dotenv", lambda: None)

    config.load_configuration()

    assert dict(os.environ) == before


def test_when_the_suite_imports_the_application_then_it_does_not_load_the_dotenv():
    """when the suite imports app.main, the developer's .env is not read.

    ``tests/conftest.py`` imports it with ``load_configuration`` replaced by a
    no-op; without that, every value of the file reaches the ``Settings()``
    that other tests build.

    Validates tests.conftest, the import of app.main.
    """
    loader_seen_by_the_entry_point = getattr(
        application_entry_point, "load_configuration", None
    )

    assert loader_seen_by_the_entry_point is not config.load_configuration
