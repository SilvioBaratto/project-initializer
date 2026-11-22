"""Dependency declarations of the FastAPI templates.

Three layers ship an ``api/pyproject.toml`` (the base, supabase and entra); the
token overlay ships none and inherits the base. No layer ships a ``requirements*.txt``:
the manifest is the single place that declares the version and the pinned
dependencies, so a dependency that no code imports is attack surface every scaffold
carries.
"""

import ast
import re
import tomllib
from pathlib import Path

import pytest

_PACKAGE = Path(__file__).resolve().parent.parent / "project_initializer"
_PYPROJECT_FILES = {
    "base": _PACKAGE / "templates-api-fastapi" / "api" / "pyproject.toml",
    "supabase": _PACKAGE / "templates-supabase-fastapi" / "api" / "pyproject.toml",
    "entra": _PACKAGE / "templates-entra-fastapi" / "api" / "pyproject.toml",
}

# Neither library is imported by any FastAPI template: the health endpoints read
# no host metrics and there is no Prometheus exposition.
_UNUSED_DEPENDENCIES = ("psutil", "prometheus-client", "prometheus_client")

_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?P<extras>\[[^\]]*\])?(?P<spec>.*)$"
)


def _manifest(variant: str) -> dict:
    with _PYPROJECT_FILES[variant].open("rb") as handle:
        return tomllib.load(handle)


def _runtime_dependencies(variant: str) -> list[str]:
    return _manifest(variant)["project"]["dependencies"]


def _dev_dependencies(variant: str) -> list[str]:
    return _manifest(variant)["project"]["optional-dependencies"]["dev"]


def _declared_dependencies(variant: str) -> list[str]:
    return _runtime_dependencies(variant) + _dev_dependencies(variant)


def _names_of(variant: str, entries: list[str]) -> set[str]:
    names: set[str] = set()
    for entry in entries:
        match = _REQUIREMENT.match(entry)
        assert match is not None, f"{variant}: unparsable dependency {entry!r}"
        names.add(match.group("name").lower())
    return names


def _dependency_names(variant: str) -> set[str]:
    return _names_of(variant, _declared_dependencies(variant))


def _imported_top_level_modules(source_root: Path) -> set[str]:
    modules: set[str] = set()
    for path in source_root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                modules.add(node.module.split(".")[0])
    return modules


@pytest.mark.parametrize("variant", sorted(_PYPROJECT_FILES))
def test_when_dependencies_are_read_then_every_dependency_is_pinned_exactly(
    variant: str,
):
    """Every runtime and dev entry pins one version with ``==``, so two scaffolds install the same set.

    Validates project_initializer/templates-{api,supabase,entra}-fastapi/api/pyproject.toml.
    """
    for entry in _declared_dependencies(variant):
        match = _REQUIREMENT.match(entry)
        assert match is not None, f"{variant}: unparsable dependency {entry!r}"
        assert match.group("spec").startswith("=="), (
            f"{variant}: {match.group('name')} is not pinned with =="
        )


@pytest.mark.parametrize("variant", sorted(_PYPROJECT_FILES))
@pytest.mark.parametrize("dependency", _UNUSED_DEPENDENCIES)
def test_when_dependencies_are_read_then_an_unused_monitoring_library_is_absent(
    variant: str, dependency: str
):
    """psutil and prometheus-client are not declared by any FastAPI variant.

    Validates project_initializer/templates-{api,supabase,entra}-fastapi/api/pyproject.toml.
    """
    assert dependency not in _dependency_names(variant), (
        f"{variant} still declares {dependency}"
    )


def test_when_the_entra_dependencies_are_read_then_pyjwt_is_on_the_audited_release():
    """PyJWT stays on 2.15.1, where a failed key-set reload keeps the cached keys.

    The unknown-kid cooldown relies on that to keep known users signed in while
    Entra's key endpoint is down.

    Validates project_initializer/templates-entra-fastapi/api/pyproject.toml.
    """
    assert "PyJWT[crypto]==2.15.1" in _runtime_dependencies("entra")


def test_when_the_base_dependencies_are_read_then_the_token_stack_is_pinned():
    """The token overlay ships no manifest and inherits these two pins.

    Validates project_initializer/templates-api-fastapi/api/pyproject.toml.
    """
    runtime = _runtime_dependencies("base")
    assert "python-jose[cryptography]==3.5.0" in runtime
    assert any(entry.startswith("bcrypt==") for entry in runtime)
    assert "passlib" not in _dependency_names("base")


def test_when_the_token_overlay_is_listed_then_it_ships_no_dependency_file():
    """The token layer inherits the base manifest; a copy would fork the pins.

    Validates project_initializer/templates-token-fastapi/api/ (absence of pyproject.toml and requirements.txt).
    """
    token_api = _PACKAGE / "templates-token-fastapi" / "api"
    assert not (token_api / "pyproject.toml").exists()
    assert not (token_api / "requirements.txt").exists()


def test_when_every_layer_is_listed_then_none_ships_a_requirements_file():
    """The Dockerfile and CI install from pyproject.toml; a requirements file would fork the pins.

    Validates project_initializer/templates*/ (absence of requirements*.txt).
    """
    shipped = sorted(
        str(path.relative_to(_PACKAGE))
        for path in _PACKAGE.glob("templates*/**/requirements*.txt")
    )
    assert shipped == []


@pytest.mark.parametrize("variant", sorted(_PYPROJECT_FILES))
def test_when_pyproject_is_parsed_then_the_project_is_named_api(variant: str):
    """The project name is the same in every variant, so the installed metadata does not depend on the auth mode.

    Validates project_initializer/templates-{api,supabase,entra}-fastapi/api/pyproject.toml [project].name.
    """
    assert _manifest(variant)["project"]["name"] == "api"


@pytest.mark.parametrize("variant", sorted(_PYPROJECT_FILES))
def test_when_pyproject_is_parsed_then_a_version_is_declared(variant: str):
    """The manifest is the single source of the service version, so it must carry one.

    Validates project_initializer/templates-{api,supabase,entra}-fastapi/api/pyproject.toml [project].version.
    """
    version = _manifest(variant)["project"].get("version")
    assert isinstance(version, str)
    assert version.strip() != "", f"{variant} declares no [project] version"


def test_when_the_three_pyproject_files_are_parsed_then_their_versions_are_equal():
    """A scaffold reports the same service version whichever auth mode it was generated with.

    Validates project_initializer/templates-{api,supabase,entra}-fastapi/api/pyproject.toml [project].version.
    """
    versions = {
        variant: _manifest(variant)["project"].get("version")
        for variant in _PYPROJECT_FILES
    }
    assert len(set(versions.values())) == 1, f"versions differ: {versions}"


@pytest.mark.parametrize("variant", sorted(_PYPROJECT_FILES))
def test_when_pyproject_is_parsed_then_no_python_package_is_listed(variant: str):
    """With an empty package list setuptools does not discover app, alembic and tests as one flat layout.

    Validates project_initializer/templates-{api,supabase,entra}-fastapi/api/pyproject.toml [tool.setuptools].packages.
    """
    assert _manifest(variant)["tool"]["setuptools"]["packages"] == []


@pytest.mark.parametrize("variant", sorted(_PYPROJECT_FILES))
def test_when_dev_dependencies_are_read_then_httpx2_carries_the_test_client(
    variant: str,
):
    """Starlette's TestClient warns when only httpx is installed, so every dev extra declares httpx2.

    Validates project_initializer/templates-{api,supabase,entra}-fastapi/api/pyproject.toml.
    """
    assert "httpx2" in _names_of(variant, _dev_dependencies(variant))


def test_when_the_base_dependencies_are_read_then_httpx_is_not_declared():
    """The base layer and the token overlay that inherits its manifest install httpx2 alone.

    Validates project_initializer/templates-api-fastapi/api/pyproject.toml.
    """
    assert "httpx" not in _dependency_names("base")


def test_when_the_httpx_less_layers_are_scanned_then_no_module_imports_httpx():
    """No layer that lands on the no-auth or token manifest installs httpx, so an import of it would fail the scaffold's own tests.

    Validates project_initializer/templates-{api,token,asyncdb}-fastapi/api (imports).
    """
    imported: set[str] = set()
    for layer in ("templates-api-fastapi", "templates-token-fastapi", "templates-asyncdb-fastapi"):
        imported |= _imported_top_level_modules(_PACKAGE / layer / "api")

    assert "httpx" not in imported


def test_when_the_supabase_dependencies_are_read_then_httpx_stays_a_runtime_dependency():
    """The Supabase client and the variant's own code need httpx beside the httpx2 test transport.

    Validates project_initializer/templates-supabase-fastapi/api/pyproject.toml.
    """
    assert "httpx" in _names_of("supabase", _runtime_dependencies("supabase"))
    imported = _imported_top_level_modules(
        _PACKAGE / "templates-supabase-fastapi" / "api" / "app"
    )
    assert "httpx" in imported
