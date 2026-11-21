"""Unit tests for where the application version comes from."""

import tomllib
from pathlib import Path

import pytest

from app.infrastructure.settings import DISTRIBUTION_NAME, Settings

pytestmark = pytest.mark.unit

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _declared_project() -> dict:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)["project"]


def test_when_settings_are_built_then_the_version_is_the_one_pyproject_declares():
    """Settings.version equals ``[project] version``; a stale install fails here.

    Validates app.infrastructure.settings.Settings.version.
    """
    assert Settings().version == _declared_project()["version"], (
        'pyproject.toml changed after the install: run pip install ".[dev]" again'
    )


def test_when_pyproject_is_read_then_its_name_is_the_distribution_the_app_looks_up():
    """The metadata key the application reads is the project name.

    Validates app.infrastructure.settings.DISTRIBUTION_NAME.
    """
    assert _declared_project()["name"] == DISTRIBUTION_NAME


def test_when_the_environment_sets_a_version_then_the_setting_ignores_it(monkeypatch):
    """No environment variable overrides the version.

    Validates app.infrastructure.settings.Settings.version.
    """
    monkeypatch.setenv("VERSION", "9.9.9")

    assert Settings().version != "9.9.9"
