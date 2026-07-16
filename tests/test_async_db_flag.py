"""Tests for the --async-db generator flag gating the FastAPI async path (#21).

Covers: flag parsing, validation rejection (nestjs / frontend), layer routing
(overlay appended only for fastapi + api/fullstack), the pure requirements
transform, and scaffold behaviour (flag-on includes async files + appended
deps; flag-off byte-identical to today).
"""

import hashlib

import pytest

import project_initializer.cli as cli
from project_initializer.cli import (
    app,
    copy_template,
    get_asyncdb_overlay_dir,
    select_layers,
    validate_scope,
)
from project_initializer.file_transforms import append_async_requirements
from typer.testing import CliRunner

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


def _tree_hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
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


# --- pure requirements transform --------------------------------------------


def test_when_requirements_transformed_async_deps_are_appended():
    """when requirements text is transformed, asyncpg and sqlalchemy[asyncio] appear."""
    out = append_async_requirements("fastapi==0.136.3\n")
    assert "asyncpg" in out
    assert "sqlalchemy[asyncio]" in out


def test_when_requirements_already_has_asyncpg_transform_is_idempotent():
    """when requirements already lists asyncpg, the transform leaves it unchanged."""
    already = "fastapi==0.136.3\nasyncpg==0.31.0\n"
    assert append_async_requirements(already) == already


# --- scaffold: flag-on includes async files + deps --------------------------


@pytest.mark.parametrize("scope", ["api", "fullstack"])
def test_when_scaffolded_with_async_db_async_files_exist(tmp_path, scope):
    """when scaffolded with --async-db, the async DB modules are present."""
    copy_template(tmp_path, "app", framework="fastapi", scope=scope, async_db=True)
    assert (tmp_path / "api" / "app" / "database_async.py").exists()
    assert (tmp_path / "api" / "app" / "repositories" / "base_async.py").exists()


def test_when_scaffolded_with_async_db_requirements_has_async_deps(tmp_path):
    """when scaffolded with --async-db, requirements.txt lists the async deps."""
    copy_template(tmp_path, "app", framework="fastapi", scope="api", async_db=True)
    reqs = (tmp_path / "api" / "requirements.txt").read_text(encoding="utf-8")
    assert "asyncpg" in reqs
    assert "sqlalchemy[asyncio]" in reqs


def test_when_supabase_scaffolded_with_async_db_requirements_has_async_deps(tmp_path):
    """when supabase is scaffolded with --async-db, its requirements gain async deps."""
    copy_template(
        tmp_path,
        "app",
        auth="supabase",
        framework="fastapi",
        scope="api",
        async_db=True,
    )
    reqs = (tmp_path / "api" / "requirements.txt").read_text(encoding="utf-8")
    assert "asyncpg" in reqs
    assert "supabase" in reqs  # the supabase overlay's own deps survive


# --- scaffold: flag-off is byte-identical to today --------------------------


@pytest.mark.parametrize("scope", ["api", "fullstack"])
@pytest.mark.parametrize("auth", [None, "token", "supabase"])
def test_when_async_db_false_scaffold_is_byte_identical_to_default(
    tmp_path, scope, auth
):
    """when async_db is False, the tree equals the no-flag default byte-for-byte."""
    default = tmp_path / "default"
    explicit = tmp_path / "explicit"
    copy_template(default, "app", auth=auth, framework="fastapi", scope=scope)
    copy_template(
        explicit, "app", auth=auth, framework="fastapi", scope=scope, async_db=False
    )
    assert _tree_hashes(default) == _tree_hashes(explicit)
