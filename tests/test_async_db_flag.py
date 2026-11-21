"""Tests for the --async-db generator flag gating the FastAPI async path (#21).

Covers: flag parsing, validation rejection (nestjs / frontend), layer routing
(overlay appended only for fastapi + api/fullstack), the pure pyproject
dependency transform, and scaffold behaviour (flag-on includes async files +
appended deps; flag-off byte-identical to today).
"""

import hashlib
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

import project_initializer.cli as cli
from project_initializer.cli import (
    app,
    copy_template,
    get_api_templates_dir,
    get_asyncdb_overlay_dir,
    select_layers,
    validate_scope,
)
from project_initializer.env_generator import GENERATED_SECRET_KEYS
from project_initializer.file_transforms import append_async_dependencies

runner = CliRunner()


def _resolved_async_db(argv, monkeypatch):
    """Run the CLI (non-interactive) and return the async_db copy_template saw."""
    calls = {}

    def spy(dest_dir, project_name=None, **kwargs):
        calls.update(kwargs)

    monkeypatch.setattr(cli, "copy_template", spy)
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, result.output
    return calls["async_db"]


def _srcs(layers):
    return [src for src, _skip, _t in layers]


def _masked_env_bytes(env_path):
    """The .env with generated secret values blanked: those differ on every scaffold."""
    lines = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, _, _ = line.partition("=")
        lines.append(f"{key}=" if key in GENERATED_SECRET_KEYS else line)
    return "\n".join(lines).encode("utf-8")


def _base_pyproject_text():
    path = get_api_templates_dir("fastapi") / "api" / "pyproject.toml"
    return path.read_text(encoding="utf-8")


def _declared_names(requirements):
    """Requirement names without their pins, so a version bump never breaks a test."""
    return {requirement.split("==")[0] for requirement in requirements}


def _scaffolded_pyproject(api_dir):
    return tomllib.loads((api_dir / "pyproject.toml").read_text(encoding="utf-8"))


def _tree_hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(
            _masked_env_bytes(p)
            if p.relative_to(root) == Path(".env")
            else p.read_bytes()
        ).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# --- flag parsing -----------------------------------------------------------


def test_when_async_db_flag_given_it_is_true(monkeypatch):
    """when --async-db is given, the resolved flag is True."""
    assert _resolved_async_db(["myapp", "--async-db"], monkeypatch) is True


def test_when_async_db_flag_omitted_it_is_false(monkeypatch):
    """when --async-db is omitted, the resolved flag is False."""
    assert _resolved_async_db(["myapp"], monkeypatch) is False


# --- validation -------------------------------------------------------------


def test_when_async_db_with_nestjs_error_is_returned():
    """when --async-db is combined with --nestjs, an error is returned."""
    assert validate_scope("fullstack", "nestjs", None, async_db=True)


def test_when_async_db_with_frontend_scope_error_is_returned():
    """when --async-db is combined with --scope frontend, an error is returned."""
    assert validate_scope("frontend", None, None, async_db=True)


@pytest.mark.parametrize("scope", ["api", "fullstack"])
def test_when_async_db_with_fastapi_scope_no_error(scope):
    """when --async-db is used with fastapi api/fullstack scope, no error is returned."""
    assert validate_scope(scope, "fastapi", None, async_db=True) == []
    assert validate_scope(scope, None, None, async_db=True) == []


# --- layer routing ----------------------------------------------------------


@pytest.mark.parametrize("scope", ["api", "fullstack"])
def test_when_async_db_set_fastapi_overlay_is_appended(scope):
    """when async_db is set for fastapi, the asyncdb overlay is the last layer."""
    layers = select_layers(scope, "fastapi", None, async_db=True)
    assert _srcs(layers)[-1] == get_asyncdb_overlay_dir()


def test_when_async_db_unset_no_overlay_layer():
    """when async_db is unset, the asyncdb overlay is not among the layers."""
    layers = select_layers("fullstack", "fastapi", None, async_db=False)
    assert get_asyncdb_overlay_dir() not in _srcs(layers)


def test_when_async_db_set_for_nestjs_no_overlay_layer():
    """when async_db is set for nestjs, the fastapi overlay is not appended."""
    layers = select_layers("fullstack", "nestjs", None, async_db=True)
    assert get_asyncdb_overlay_dir() not in _srcs(layers)


# --- pure pyproject dependency transform -------------------------------------


def test_when_pyproject_transformed_then_async_runtime_deps_join_dependencies():
    """when pyproject text is transformed, asyncpg and sqlalchemy[asyncio] join [project] dependencies.

    Validates project_initializer/file_transforms.py append_async_dependencies().
    """
    parsed = tomllib.loads(append_async_dependencies(_base_pyproject_text()))
    assert {"asyncpg", "sqlalchemy[asyncio]"} <= _declared_names(
        parsed["project"]["dependencies"]
    )


def test_when_pyproject_transformed_then_aiosqlite_joins_dev_extra():
    """when pyproject text is transformed, aiosqlite joins the dev extra and not the runtime set.

    Validates project_initializer/file_transforms.py append_async_dependencies().
    """
    parsed = tomllib.loads(append_async_dependencies(_base_pyproject_text()))
    assert "aiosqlite" in _declared_names(
        parsed["project"]["optional-dependencies"]["dev"]
    )
    assert "aiosqlite" not in _declared_names(parsed["project"]["dependencies"])


def test_when_pyproject_transformed_then_existing_dependencies_survive():
    """when pyproject text is transformed, every pre-existing dependency is still declared.

    Validates project_initializer/file_transforms.py append_async_dependencies().
    """
    original = tomllib.loads(_base_pyproject_text())["project"]
    parsed = tomllib.loads(append_async_dependencies(_base_pyproject_text()))["project"]
    assert set(original["dependencies"]) <= set(parsed["dependencies"])
    assert set(original["optional-dependencies"]["dev"]) <= set(
        parsed["optional-dependencies"]["dev"]
    )


def test_when_pyproject_transformed_twice_then_second_pass_changes_nothing():
    """when the transform runs on its own output, the text is unchanged.

    Validates project_initializer/file_transforms.py append_async_dependencies().
    """
    once = append_async_dependencies(_base_pyproject_text())
    assert append_async_dependencies(once) == once


def test_when_pyproject_already_has_asyncpg_then_transform_returns_it_unchanged():
    """when pyproject text already lists asyncpg, the transform leaves it unchanged.

    Validates project_initializer/file_transforms.py append_async_dependencies().
    """
    already = '[project]\ndependencies = [\n    "asyncpg==0.31.0",\n]\n'
    assert append_async_dependencies(already) == already


@pytest.mark.parametrize(
    ("body", "missing_array"),
    [
        ('[project]\nname = "api"\n', "dependencies"),
        ('[project]\ndependencies = [\n    "fastapi==1.0.0",\n]\n', "dev"),
    ],
    ids=["no-dependencies-array", "no-dev-array"],
)
def test_when_pyproject_lacks_an_array_then_transform_raises_value_error(
    body, missing_array
):
    """when the dependencies or dev array is missing, the transform raises instead of dropping the deps.

    Validates project_initializer/file_transforms.py append_async_dependencies().
    """
    with pytest.raises(ValueError, match=missing_array):
        append_async_dependencies(body)


# --- scaffold: flag-on includes async files + deps --------------------------


@pytest.mark.parametrize("scope", ["api", "fullstack"])
def test_when_scaffolded_with_async_db_async_files_exist(tmp_path, scope):
    """when scaffolded with --async-db, the async DB modules are present.

    Validates project_initializer/cli.py copy_template() and project_initializer/templates-asyncdb-fastapi/api/app/infrastructure.
    """
    copy_template(tmp_path, "app", framework="fastapi", scope=scope, async_db=True)
    assert (tmp_path / "api" / "app" / "infrastructure" / "database_async.py").exists()
    assert (
        tmp_path / "api" / "app" / "infrastructure" / "repositories" / "item_async.py"
    ).exists()


def test_when_scaffolded_with_async_db_then_pyproject_declares_async_deps(tmp_path):
    """when scaffolded with --async-db, api/pyproject.toml declares the async deps.

    Validates project_initializer/cli.py _dependencies_handler() and project_initializer/file_transforms.py append_async_dependencies().
    """
    copy_template(tmp_path, "app", framework="fastapi", scope="api", async_db=True)
    project = _scaffolded_pyproject(tmp_path / "api")["project"]
    assert {"asyncpg", "sqlalchemy[asyncio]"} <= _declared_names(
        project["dependencies"]
    )
    assert "aiosqlite" in _declared_names(project["optional-dependencies"]["dev"])


def test_when_scaffolded_with_async_db_then_no_requirements_txt_exists(tmp_path):
    """when scaffolded with --async-db, the dependencies live in pyproject.toml only.

    Validates project_initializer/cli.py copy_template().
    """
    copy_template(tmp_path, "app", framework="fastapi", scope="api", async_db=True)
    assert not (tmp_path / "api" / "requirements.txt").exists()


def test_when_supabase_scaffolded_with_async_db_then_pyproject_gains_async_deps(
    tmp_path,
):
    """when supabase is scaffolded with --async-db, its pyproject gains the async deps.

    Validates project_initializer/cli.py _dependencies_handler() and project_initializer/templates-supabase-fastapi/api/pyproject.toml.
    """
    copy_template(
        tmp_path,
        "app",
        auth="supabase",
        framework="fastapi",
        scope="api",
        async_db=True,
    )
    project = _scaffolded_pyproject(tmp_path / "api")["project"]
    declared = _declared_names(project["dependencies"])
    assert {"asyncpg", "sqlalchemy[asyncio]"} <= declared
    assert "supabase" in declared  # the supabase overlay's own deps survive
    assert "aiosqlite" in _declared_names(project["optional-dependencies"]["dev"])
    assert not (tmp_path / "api" / "requirements.txt").exists()


# --- scaffold: flag-off is byte-identical to today --------------------------


@pytest.mark.parametrize("scope", ["api", "fullstack"])
@pytest.mark.parametrize("auth", [None, "token", "supabase"])
def test_when_async_db_false_scaffold_is_byte_identical_to_default(
    tmp_path, scope, auth
):
    """when async_db is False, the tree equals the no-flag default byte-for-byte.

    The root .env is compared with its generated secret values blanked, because
    every scaffold draws fresh ones.

    Validates project_initializer/cli.py copy_template().
    """
    default = tmp_path / "default"
    explicit = tmp_path / "explicit"
    copy_template(default, "app", auth=auth, framework="fastapi", scope=scope)
    copy_template(
        explicit, "app", auth=auth, framework="fastapi", scope=scope, async_db=False
    )
    assert _tree_hashes(default) == _tree_hashes(explicit)
