"""Runtime data files beside the package modules ship in the wheel and the sdist.

`env_defaults.env` sat next to the modules but outside every package-data glob, so the
wheels up to 0.4.0 left it out. `cli.py` and `env_generator.py` then fell back to empty
values: a scaffold from the PyPI package wrote a root `.env` with an empty DATABASE_URL,
AUTH_TOKEN and Entra IDs, while the same scaffold from a checkout got working defaults.
The tests here read the checkout, so only a built wheel shows that gap.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent

# Non-Python files at the package root. Template overlays are packaged by their own globs.
_RUNTIME_DATA_FILES = ["env_defaults.env", "py.typed"]


def _git_ls_files(*paths: str) -> list[str]:
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    result = subprocess.run(
        ["git", "ls-files", *paths], cwd=_ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        pytest.skip("not a git checkout")
    return result.stdout.splitlines()


def test_when_package_root_is_listed_then_every_tracked_data_file_is_declared() -> None:
    """A new data file beside the modules must join _RUNTIME_DATA_FILES, so the checks below cover it."""
    root_files = [
        Path(path).name
        for path in _git_ls_files("project_initializer")
        if path.count("/") == 1 and not path.endswith(".py")
    ]
    assert sorted(root_files) == sorted(_RUNTIME_DATA_FILES)


@pytest.mark.parametrize("name", _RUNTIME_DATA_FILES)
def test_when_pyproject_package_data_is_read_then_runtime_data_file_is_listed(name: str) -> None:
    tomllib = pytest.importorskip("tomllib")
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = config["tool"]["setuptools"]["package-data"]["project_initializer"]
    assert name in patterns, f"pyproject.toml package-data must list {name!r}, or the wheel leaves it out"


@pytest.mark.parametrize("name", _RUNTIME_DATA_FILES)
def test_when_manifest_in_is_read_then_runtime_data_file_is_included(name: str) -> None:
    lines = (_ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    expected = f"include project_initializer/{name}"
    assert expected in lines, f"MANIFEST.in must contain {expected!r}, or the sdist leaves it out"


@pytest.mark.integration
def test_when_wheel_is_built_then_every_tracked_package_file_is_inside(tmp_path: Path) -> None:
    """Builds a wheel from the tracked files of this checkout and looks for each package file in it."""
    pytest.importorskip("build")
    tracked = _git_ls_files("pyproject.toml", "README.md", "LICENSE", "MANIFEST.in", "project_initializer")
    source = tmp_path / "source"
    for relative in tracked:
        origin = _ROOT / relative
        if origin.is_file():
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, target)

    dist = tmp_path / "dist"
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist), str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]

    [wheel] = dist.glob("*.whl")
    packaged = set(zipfile.ZipFile(wheel).namelist())
    expected = [
        path
        for path in tracked
        if path.startswith("project_initializer/") and not path.endswith(".pyc") and (_ROOT / path).is_file()
    ]
    missing = [path for path in expected if path not in packaged]
    assert not missing, f"{len(missing)} tracked package files are missing from the wheel: {missing[:10]}"
