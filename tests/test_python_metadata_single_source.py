"""Keeps the Python version and dependencies in ``pyproject.toml`` alone.

A Python project declares its version and its dependencies once, in ``pyproject.toml``.
These guards read the real ``project_initializer/`` tree and fresh scaffolds, so a
``requirements.txt``, a ``__version__`` or a hardcoded version string that comes back
fails here and names the file.
"""

import ast
import fnmatch
import os
import re
import tomllib
from collections.abc import Callable, Iterator
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest
from typer.testing import CliRunner

from project_initializer.cli import _installed_version, app, copy_template

_REPO = Path(__file__).resolve().parent.parent
_PACKAGE = _REPO / "project_initializer"

_DISTRIBUTION = "project-initializer"
_REQUIREMENTS_PATTERN = "requirements*.txt"
_FASTAPI_TEMPLATES_PATTERN = "templates*fastapi*"
_SKIPPED_DIRECTORIES = frozenset({"node_modules", "__pycache__", ".angular"})

# Whole-string match: a pin such as "asyncpg==0.31.0" or an address such as "0.0.0.0"
# is not a version, and must not trip the guards.
_BARE_VERSION = re.compile(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+|-[0-9A-Za-z.]+)?")
_REQUIREMENT_NAME = re.compile(r"[A-Za-z0-9_.-]+")

_API_VARIANTS = [
    pytest.param((None, False), id="fastapi"),
    pytest.param(("supabase", False), id="fastapi-supabase"),
    pytest.param(("entra", False), id="fastapi-entra"),
    pytest.param((None, True), id="fastapi-async-db"),
]

_NON_PYTHON_SCAFFOLDS = [
    pytest.param({"framework": "nestjs"}, id="nestjs"),
    pytest.param({"scope": "frontend"}, id="frontend"),
]

runner = CliRunner()


def _files_under(root: Path) -> Iterator[Path]:
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = [
            name for name in subdirectories if name not in _SKIPPED_DIRECTORIES
        ]
        for name in names:
            yield Path(directory) / name


def _is_requirements_file(path: Path) -> bool:
    return fnmatch.fnmatch(path.name.lower(), _REQUIREMENTS_PATTERN)


def _is_pyproject(path: Path) -> bool:
    return path.name == "pyproject.toml"


def _matching(root: Path, predicate: Callable[[Path], bool]) -> list[str]:
    return sorted(
        str(path.relative_to(root)) for path in _files_under(root) if predicate(path)
    )


def _read_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _bare_version(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value if _BARE_VERSION.fullmatch(node.value) else None
    return None


def _assigned_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.AnnAssign):
        targets = [node.target]
    elif isinstance(node, ast.Assign):
        targets = node.targets
    else:
        return []
    return [target.id for target in targets if isinstance(target, ast.Name)]


def _declares_version(node: ast.AST) -> bool:
    """Whether ``node`` binds ``__version__`` or binds ``version`` to a bare version."""
    names = _assigned_names(node)
    if "__version__" in names:
        return True
    return (
        "version" in names and _bare_version(getattr(node, "value", None)) is not None
    )


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _version_declarations(path: Path) -> Iterator[str]:
    for node in ast.walk(_parsed(path)):
        if _declares_version(node):
            yield f"{path.relative_to(_PACKAGE)}:{node.lineno} binds a version"


def _version_literals(path: Path) -> Iterator[str]:
    for node in ast.walk(_parsed(path)):
        literal = _bare_version(node)
        if literal is not None:
            yield f"{path.relative_to(_PACKAGE)}:{node.lineno} holds {literal!r}"


def _cli_modules() -> list[Path]:
    return sorted(_PACKAGE.glob("*.py"))


def _fastapi_template_modules() -> list[Path]:
    return sorted(
        path
        for template in _PACKAGE.glob(_FASTAPI_TEMPLATES_PATTERN)
        for path in _files_under(template)
        if path.suffix == ".py"
    )


def _scaffold(root: Path, **options) -> Path:
    copy_template(root, "app", **options)
    return root


def _requirement_names(requirements: list[str]) -> set[str]:
    return {
        match.group().lower()
        for requirement in requirements
        if (match := _REQUIREMENT_NAME.match(requirement))
    }


def _installed_metadata_version() -> str:
    try:
        return version(_DISTRIBUTION)
    except PackageNotFoundError:
        pytest.skip(f"{_DISTRIBUTION} is not installed, so it has no metadata to read")


@pytest.fixture(scope="module", params=_API_VARIANTS)
def api_scaffold(request, tmp_path_factory) -> Path:
    """Scaffold one FastAPI variant per ``_API_VARIANTS`` entry, once for the module.

    Returns:
        The scaffold root; ``--scope api`` puts the project under its ``api/``.
    """
    auth, async_db = request.param
    return _scaffold(
        tmp_path_factory.mktemp("api"),
        framework="fastapi",
        auth=auth,
        scope="api",
        async_db=async_db,
    )


# --- the scaffolder itself ---------------------------------------------------


def test_when_the_guarded_trees_are_listed_then_modules_are_found_to_scan():
    """The CLI modules and the FastAPI template modules exist, so a scan cannot pass on an empty list.

    Validates project_initializer/*.py and project_initializer/templates*fastapi*/.
    """
    assert _cli_modules()
    assert _fastapi_template_modules()


def test_when_the_package_tree_is_walked_then_no_requirements_file_exists():
    """No ``requirements*.txt`` ships in the package, in any letter case.

    Validates project_initializer/ file names.
    """
    assert _matching(_PACKAGE, _is_requirements_file) == []


def test_when_the_repo_root_is_listed_then_it_holds_no_requirements_file():
    """No ``requirements*.txt`` sits at the repository root.

    Validates the repository root file names.
    """
    root_files = [path for path in _REPO.iterdir() if path.is_file()]

    assert [path.name for path in root_files if _is_requirements_file(path)] == []


def test_when_the_package_init_is_parsed_then_it_declares_no_version():
    """``__init__.py`` binds no ``__version__`` and holds no version-looking string.

    Validates project_initializer/__init__.py.
    """
    init = _PACKAGE / "__init__.py"

    assert list(_version_declarations(init)) == []
    assert list(_version_literals(init)) == []


def test_when_the_cli_modules_are_parsed_then_none_declares_or_hardcodes_a_version():
    """No module directly under the package binds ``__version__`` or holds a bare ``X.Y.Z`` string.

    Validates project_initializer/*.py.
    """
    offenders = [
        finding
        for module in _cli_modules()
        for finding in (*_version_declarations(module), *_version_literals(module))
    ]

    assert offenders == []


def test_when_the_fastapi_templates_are_parsed_then_none_declares_a_version():
    """No FastAPI template module binds ``__version__`` or ``version`` to a bare version.

    Validates project_initializer/templates*fastapi*/ Python modules.
    """
    offenders = [
        finding
        for module in _fastapi_template_modules()
        for finding in _version_declarations(module)
    ]

    assert offenders == []


def test_when_the_root_pyproject_is_read_then_it_declares_the_version_statically():
    """The package version is a literal in ``[project]``, not computed elsewhere.

    Validates pyproject.toml [project] version.
    """
    project = _read_toml(_REPO / "pyproject.toml")["project"]

    assert _BARE_VERSION.fullmatch(project["version"])
    assert "version" not in project.get("dynamic", [])


def test_when_the_root_pyproject_is_read_then_the_python_floor_is_3_11_and_classifiers_match():
    """The supported interpreters named in the classifiers agree with the floor.

    typer 0.29 and hypothesis 6.169 no longer install on 3.10, which is end of life,
    so a 3.10 classifier or a ``>=3.10`` floor would advertise an install that fails.

    Validates pyproject.toml.
    """
    project = _read_toml(_REPO / "pyproject.toml")["project"]
    classifiers = set(project["classifiers"])
    supported = {
        f"Programming Language :: Python :: 3.{minor}" for minor in range(11, 16)
    }

    assert project["requires-python"] == ">=3.11"
    assert supported <= classifiers
    assert "Programming Language :: Python :: 3.10" not in classifiers


# --- the FastAPI scaffolds -----------------------------------------------------


def test_when_a_fastapi_api_is_scaffolded_then_its_pyproject_declares_version_and_dependencies(
    api_scaffold,
):
    """The scaffolded API carries its version and dependencies in ``api/pyproject.toml``.

    Validates project_initializer/templates-{api,supabase,entra}-fastapi/api/pyproject.toml.
    """
    pyproject = api_scaffold / "api" / "pyproject.toml"

    project = _read_toml(pyproject)["project"]

    assert project["version"]
    assert project["dependencies"]


def test_when_a_fastapi_api_is_scaffolded_then_no_requirements_file_exists(
    api_scaffold,
):
    """No ``requirements*.txt`` is written anywhere in the scaffold.

    Validates project_initializer/cli.py copy_template().
    """
    assert _matching(api_scaffold, _is_requirements_file) == []


def test_when_a_fastapi_api_is_scaffolded_then_no_pyproject_sits_at_the_root(
    api_scaffold,
):
    """The only ``pyproject.toml`` is the API's own, never one at the project root.

    Validates project_initializer/cli.py copy_template().
    """
    assert _matching(api_scaffold, _is_pyproject) == ["api/pyproject.toml"]


def test_when_async_db_is_scaffolded_then_asyncpg_is_a_dependency_and_aiosqlite_a_dev_one(
    tmp_path,
):
    """The async overlay extends ``dependencies`` and the ``dev`` extra of ``api/pyproject.toml``.

    Validates project_initializer/file_transforms.py append_async_dependencies().
    """
    _scaffold(tmp_path, framework="fastapi", scope="api", async_db=True)

    project = _read_toml(tmp_path / "api" / "pyproject.toml")["project"]

    assert "asyncpg" in _requirement_names(project["dependencies"])
    assert "aiosqlite" in _requirement_names(project["optional-dependencies"]["dev"])


# --- the projects that are not Python -----------------------------------------


@pytest.mark.parametrize("options", _NON_PYTHON_SCAFFOLDS)
def test_when_a_non_python_project_is_scaffolded_then_it_holds_no_python_metadata(
    tmp_path, options
):
    """A NestJS or frontend-only scaffold has no ``pyproject.toml`` and no ``requirements*.txt``.

    Validates project_initializer/cli.py copy_template().
    """
    _scaffold(tmp_path, **options)

    assert _matching(tmp_path, _is_pyproject) == []
    assert _matching(tmp_path, _is_requirements_file) == []


# --- the --version option -----------------------------------------------------


def test_when_version_flag_is_given_then_the_cli_prints_the_installed_metadata_version():
    """``--version`` prints the version the installed distribution reports.

    Validates project_initializer/cli.py _version_callback().
    """
    installed = _installed_metadata_version()

    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"{_DISTRIBUTION} {installed}"


def test_when_the_installed_version_is_asked_then_it_is_the_metadata_version():
    """``_installed_version()`` returns what the installed distribution reports.

    Validates project_initializer/cli.py _installed_version().
    """
    assert _installed_version() == _installed_metadata_version()


def test_when_the_package_is_not_installed_then_the_version_flag_still_exits_cleanly(
    monkeypatch,
):
    """A source tree without metadata says it has no version instead of crashing.

    Validates project_initializer/cli.py _installed_version().
    """

    def not_installed(_distribution: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr("project_initializer.cli.version", not_installed)

    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0, result.output
    assert result.output.startswith(f"{_DISTRIBUTION} ")
    assert "not installed" in result.output
