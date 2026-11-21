"""Guard: every scaffolded FastAPI variant ships migrations that match its ORM.

Alembic owns the schema of a FastAPI project: the application never calls
``create_all``, and ``entrypoint.sh`` runs ``alembic upgrade head``. A variant whose
migrations and models disagree therefore starts against a database that lacks a
table, or has one it does not use.

The overlay system is what resolves the difference between variants. The supabase
overlay maps its user model to ``profiles`` instead of ``users``, and its migration
reuses the base migration's *file name*, so it overwrites that file instead of
stacking next to it. If it stacked, a supabase scaffold would apply both and create a
stray ``users`` table, hence the exact-table assertions below.

Every downgrade must also keep the data: a table is never dropped directly but
through ``preserve_and_drop_table``, which copies the rows aside first. On
PostgreSQL those backups live in the ``migration_backup`` schema, away from the
tables the Supabase Data API serves.

The supabase layer ships a second migration, ``0003_enable_row_level_security``, with
no counterpart in the base: it exists only there, so no other variant enables row
level security.
"""

import ast
import re
from pathlib import Path

import pytest

from project_initializer.cli import copy_template

_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "project_initializer"
_BASE_VERSIONS = _PACKAGE_DIR / "templates-api-fastapi" / "api" / "alembic" / "versions"
_SUPABASE_VERSIONS = (
    _PACKAGE_DIR / "templates-supabase-fastapi" / "api" / "alembic" / "versions"
)
_BASE_API = _PACKAGE_DIR / "templates-api-fastapi" / "api"
_MIGRATION_SAFETY = _BASE_API / "app" / "infrastructure" / "migration_safety.py"
_ALEMBIC_INI = _BASE_API / "alembic.ini"
_ALEMBIC_ENV = _BASE_API / "alembic" / "env.py"
_USERS_MIGRATION = "0002_create_users_table.py"
_RLS_MIGRATION = "0003_enable_row_level_security.py"
_VERSION_TABLE = "alembic_version"

# The tables each variant's migrations create, in migration order: the shared `items`
# sample first, then the variant's own user model.
_USER_TABLE_BY_AUTH = {
    None: "users",
    "token": "users",
    "entra": "users",
    "supabase": "profiles",
}

# (auth, async_db): the async overlay adds no table, so one async variant is enough.
_VARIANTS = [
    pytest.param((None, False), id="none"),
    pytest.param(("token", False), id="token"),
    pytest.param(("supabase", False), id="supabase"),
    pytest.param(("entra", False), id="entra"),
    pytest.param((None, True), id="none-async"),
]

_CREATE_TABLE = re.compile(r"""op\.create_table\(\s*["']([^"']+)["']""")
_PRESERVE_TABLE = re.compile(r"""preserve_and_drop_table\(\s*["']([^"']+)["']""")
_TABLENAME = re.compile(r"""__tablename__\s*=\s*["']([^"']+)["']""")


def _expected_tables(auth):
    return ["items", _USER_TABLE_BY_AUTH[auth]]


@pytest.fixture(scope="module", params=_VARIANTS)
def variant(request, tmp_path_factory):
    """Scaffold one FastAPI variant once and return ``(auth, async_db, api_dir)``."""
    auth, async_db = request.param
    root = tmp_path_factory.mktemp("fastapi-migrations")
    copy_template(
        root, "app", auth=auth, framework="fastapi", scope="api", async_db=async_db
    )
    return auth, async_db, root / "api"


def _migration_files(versions_dir: Path) -> list[Path]:
    return sorted(
        path for path in versions_dir.glob("*.py") if path.name != "__init__.py"
    )


def _migration_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _created_tables(versions_dir: Path) -> list[str]:
    """Every table the variant's migrations create, in file order."""
    tables: list[str] = []
    for path in _migration_files(versions_dir):
        tables += _CREATE_TABLE.findall(_migration_text(path))
    return tables


def _orm_tables(api_dir: Path) -> set[str]:
    """Every table the variant's ORM records map to."""
    orm_dir = api_dir / "app" / "infrastructure" / "orm"
    return {
        table
        for path in orm_dir.glob("*.py")
        for table in _TABLENAME.findall(path.read_text(encoding="utf-8"))
    }


def _function(path: Path, name: str) -> ast.FunctionDef | None:
    tree = ast.parse(_migration_text(path))
    return next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ),
        None,
    )


def _has_real_body(function: ast.FunctionDef) -> bool:
    """False for a stub: only a docstring, ``pass`` or ``raise NotImplementedError``."""
    for statement in function.body:
        if isinstance(statement, ast.Pass):
            continue
        if isinstance(statement, ast.Expr) and isinstance(
            statement.value, ast.Constant
        ):
            continue
        if isinstance(statement, ast.Raise) and "NotImplementedError" in ast.dump(
            statement
        ):
            continue
        return True
    return False


def _module_constant(path: Path, name: str):
    tree = ast.parse(_migration_text(path))
    for node in tree.body:
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            target, value = node.targets[0].id, node.value
        if target == name and isinstance(value, ast.Constant):
            return value.value
    return None


def _literal_constant(path: Path, name: str):
    """Evaluate a module-level constant such as a tuple of names, without importing."""
    for node in ast.parse(_migration_text(path)).body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        ):
            return ast.literal_eval(node.value)
    return None


@pytest.mark.integration
def test_scaffolded_fastapi_ships_alembic_with_a_migration(variant):
    """`alembic upgrade head` must have something to apply, or the database stays empty.

    Validates project_initializer/templates-api-fastapi/api/alembic.ini, project_initializer/templates-api-fastapi/api/alembic/env.py and project_initializer/templates-{api,supabase}-fastapi/api/alembic/versions.
    """
    _, _, api_dir = variant
    versions = api_dir / "alembic" / "versions"

    assert (api_dir / "alembic.ini").is_file()
    assert (api_dir / "alembic" / "env.py").is_file()
    assert _migration_files(versions), (
        "alembic/versions has no migration: the entrypoint's `alembic upgrade head` "
        "would create no tables"
    )


@pytest.mark.integration
def test_scaffolded_fastapi_migrations_create_exactly_the_orm_tables(variant):
    """The merged migrations create the tables the variant's ORM maps to, and no others.

    Supabase maps its user model to ``profiles``; the others to ``users``; all add
    ``items``. Asserting the exact list also catches the overlay stacking failure: a
    supabase scaffold that kept the base users migration beside its own would create
    ``users`` as well.

    Validates project_initializer/templates-{api,supabase}-fastapi/api/alembic/versions against the ORM models in project_initializer/templates-api-fastapi/api/app/infrastructure/orm.
    """
    auth, _, api_dir = variant

    created = _created_tables(api_dir / "alembic" / "versions")

    assert created == _expected_tables(auth), (
        f"fastapi+{auth or 'none'}: migrations create {created}, expected exactly "
        f"{_expected_tables(auth)}"
    )
    assert set(created) == _orm_tables(api_dir), (
        f"fastapi+{auth or 'none'}: the ORM maps {sorted(_orm_tables(api_dir))} but the "
        f"migrations create {sorted(set(created))}; regenerate with "
        "`alembic revision --autogenerate`"
    )


@pytest.mark.integration
def test_scaffolded_fastapi_migrations_form_one_linear_chain(variant):
    """Revisions chain from the first migration to a single head, each naming its parent.

    Validates project_initializer/templates-{api,supabase}-fastapi/api/alembic/versions revision chain.
    """
    _, _, api_dir = variant
    revisions = [
        (
            _module_constant(path, "revision"),
            _module_constant(path, "down_revision"),
        )
        for path in _migration_files(api_dir / "alembic" / "versions")
    ]

    parent = None
    for revision, down_revision in revisions:
        assert revision, "a migration has no `revision` constant"
        assert down_revision == parent, (
            f"{revision} descends from {down_revision!r}, expected {parent!r}: the "
            "migration chain is broken or has a second head"
        )
        parent = revision


@pytest.mark.integration
def test_scaffolded_fastapi_every_migration_has_a_real_downgrade(variant):
    """Each migration defines a downgrade that does something, not a stub.

    Validates project_initializer/templates-{api,supabase}-fastapi/api/alembic/versions downgrade().
    """
    _, _, api_dir = variant

    for path in _migration_files(api_dir / "alembic" / "versions"):
        downgrade = _function(path, "downgrade")
        assert downgrade is not None, f"{path.name} has no downgrade()"
        assert _has_real_body(downgrade), (
            f"{path.name}: downgrade() is a stub, so the migration cannot be rolled back"
        )


@pytest.mark.integration
def test_scaffolded_fastapi_downgrades_preserve_the_rows_they_drop(variant):
    """A downgrade copies a table aside before dropping it, so a rollback loses no data.

    Validates project_initializer/templates-{api,supabase}-fastapi/api/alembic/versions downgrade().
    """
    _, _, api_dir = variant

    for path in _migration_files(api_dir / "alembic" / "versions"):
        text = _migration_text(path)
        assert "op.drop_table(" not in text, (
            f"{path.name} drops a table directly: use preserve_and_drop_table so the "
            "rows survive the rollback"
        )
        assert sorted(_PRESERVE_TABLE.findall(text)) == sorted(
            _CREATE_TABLE.findall(text)
        ), (
            f"{path.name}: the tables its downgrade preserves differ from the tables "
            "its upgrade creates"
        )


def test_supabase_users_migration_replaces_the_base_file_by_name():
    """The supabase 0002 migration has the base file's name, so it overwrites it.

    Layers overwrite by path. A different name would leave both files in a supabase
    scaffold and create a stray ``users`` table next to ``profiles``.

    Validates project_initializer/templates-supabase-fastapi/api/alembic/versions/0002_create_users_table.py.
    """
    base_names = {path.name for path in _migration_files(_BASE_VERSIONS)}
    supabase_names = {path.name for path in _migration_files(_SUPABASE_VERSIONS)}

    assert supabase_names, "the supabase layer ships no migration"
    assert _USERS_MIGRATION in supabase_names
    assert _USERS_MIGRATION in base_names, (
        "the supabase users migration would sit beside the base migrations instead "
        "of replacing one"
    )
    supabase_file = _SUPABASE_VERSIONS / _USERS_MIGRATION
    base_file = _BASE_VERSIONS / _USERS_MIGRATION
    assert _CREATE_TABLE.findall(_migration_text(supabase_file)) == ["profiles"]
    assert _CREATE_TABLE.findall(_migration_text(base_file)) == ["users"]


def test_supabase_row_level_security_migration_exists_only_in_the_supabase_layer():
    """0003 is not shipped by the base, so no other variant enables row level security.

    It is the only supabase migration that has no base file to replace, and it
    must chain onto the supabase profiles migration, not onto the base users one.

    Validates project_initializer/templates-supabase-fastapi/api/alembic/versions/0003_enable_row_level_security.py.
    """
    base_names = {path.name for path in _migration_files(_BASE_VERSIONS)}
    supabase_names = {path.name for path in _migration_files(_SUPABASE_VERSIONS)}

    assert supabase_names == {_USERS_MIGRATION, _RLS_MIGRATION}
    assert _RLS_MIGRATION not in base_names
    rls = _SUPABASE_VERSIONS / _RLS_MIGRATION
    profiles = _SUPABASE_VERSIONS / _USERS_MIGRATION
    assert _module_constant(rls, "down_revision") == _module_constant(
        profiles, "revision"
    )


def test_supabase_row_level_security_migration_enables_it_on_every_table():
    """0003 secures items, profiles and the Alembic bookkeeping table.

    Supabase serves every ``public`` table through its Data API and the single-page
    app ships the publishable key, so a table without row level security is open
    to anybody holding that key, ``alembic_version`` included.

    Validates project_initializer/templates-supabase-fastapi/api/alembic/versions/0003_enable_row_level_security.py.
    """
    path = _SUPABASE_VERSIONS / _RLS_MIGRATION
    text = _migration_text(path)

    assert set(_literal_constant(path, "SECURED_TABLES")) == {
        "items",
        "profiles",
        _VERSION_TABLE,
    }
    assert "ENABLE" in text and "DISABLE" in text
    assert _function(path, "upgrade") is not None
    assert _function(path, "downgrade") is not None
    assert "FORCE" not in text, (
        "forcing row level security would lock out the API, which connects as the "
        "table owner"
    )
    assert "POSTGRESQL_DIALECT" in text, "SQLite has no row level security"
    assert "CREATE POLICY" not in text.upper(), (
        "a policy would open a table to the Data API roles; add one deliberately in "
        "a later migration"
    )


@pytest.mark.integration
def test_scaffolded_fastapi_enables_row_level_security_on_supabase_only(variant):
    """A supabase scaffold secures every table its migrations create; the rest ship no 0003.

    Validates project_initializer/templates-supabase-fastapi/api/alembic/versions/0003_enable_row_level_security.py.
    """
    auth, _, api_dir = variant
    versions = api_dir / "alembic" / "versions"
    rls = versions / _RLS_MIGRATION

    if auth != "supabase":
        assert not rls.exists(), (
            f"fastapi+{auth or 'none'} must not enable row level security"
        )
        return
    secured = set(_literal_constant(rls, "SECURED_TABLES"))
    assert secured == set(_created_tables(versions)) | {_VERSION_TABLE}, (
        "a table the migrations create is missing from SECURED_TABLES, or a secured "
        "table does not exist"
    )


def test_migration_backups_go_to_the_backup_schema_on_postgresql_only():
    """Rows a downgrade preserves are copied into ``migration_backup`` on PostgreSQL.

    A backup in ``public`` would be served by the Supabase Data API without the
    access rules of the table it copies. SQLite has no schemas, so there the backup
    sits beside the table.

    Validates project_initializer/templates-api-fastapi/api/app/infrastructure/migration_safety.py.
    """
    source = _MIGRATION_SAFETY.read_text(encoding="utf-8")

    assert _module_constant(_MIGRATION_SAFETY, "BACKUP_SCHEMA") == "migration_backup"
    assert _module_constant(_MIGRATION_SAFETY, "POSTGRESQL_DIALECT") == "postgresql"
    assert "BACKUP_SCHEMA if dialect_name == POSTGRESQL_DIALECT else None" in source
    assert "CREATE SCHEMA IF NOT EXISTS" in source
    assert "schema == BACKUP_SCHEMA" in source, "autogenerate must skip backup tables"


def test_migration_backup_names_carry_a_microsecond_timestamp():
    """Two downgrades inside one second must not collide on the backup table name.

    Validates project_initializer/templates-api-fastapi/api/app/infrastructure/migration_safety.py.
    """
    assert (
        _module_constant(_MIGRATION_SAFETY, "BACKUP_TIMESTAMP_FORMAT")
        == "%Y%m%d%H%M%S%f"
    )
    assert _module_constant(_MIGRATION_SAFETY, "BACKUP_TIMESTAMP_DIGITS") == 20


def test_migration_safety_offers_table_and_column_preservation():
    """A drafted drop becomes a backup-then-drop call, for tables and for columns.

    Validates project_initializer/templates-api-fastapi/api/app/infrastructure/migration_safety.py.
    """
    source = _MIGRATION_SAFETY.read_text(encoding="utf-8")

    for name in (
        "def preserve_and_drop_table",
        "def preserve_and_drop_column",
        "def preserve_dropped_tables",
        "class PreserveAndDropTableOp",
        "def include_object",
    ):
        assert name in source
    assert "isinstance(operation, ops.DropTableOp)" in source


def test_alembic_environment_is_wired_for_safe_drafts_and_structured_logs():
    """alembic.ini and env.py carry the settings the migration runbook promises.

    The revision id is the file name, drafted drops are rewritten, backup tables
    stay out of autogenerate, the output goes through the application's logger, and
    a caller that embeds the migrations can leave the environment alone.

    Validates project_initializer/templates-api-fastapi/api/alembic.ini and project_initializer/templates-api-fastapi/api/alembic/env.py.
    """
    ini = _ALEMBIC_INI.read_text(encoding="utf-8")
    env = _ALEMBIC_ENV.read_text(encoding="utf-8")

    assert re.search(r"^file_template = %%\(rev\)s$", ini, re.M)
    assert "sqlalchemy.url" not in "".join(
        line for line in ini.splitlines() if not line.lstrip().startswith("#")
    )
    assert "fileConfig(" not in env
    assert "configure_logging(settings.log_level, settings.log_format)" in env
    assert "process_revision_directives=preserve_dropped_tables" in env
    assert "include_object=include_object" in env
    assert 'EMBEDDED_ATTRIBUTE = "embedded"' in env
    assert "hide_parameters=True" in env


def test_items_migration_creates_and_drops_the_created_at_index():
    """The newest-first listing is served by ``idx_items_created_at``, from 0001 on.

    Validates project_initializer/templates-api-fastapi/api/alembic/versions/0001_create_items_table.py.
    """
    path = _BASE_VERSIONS / "0001_create_items_table.py"
    text = _migration_text(path)

    assert _module_constant(path, "CREATED_AT_INDEX") == "idx_items_created_at"
    assert "op.create_index(CREATED_AT_INDEX" in text
    assert 'preserve_and_drop_table("items", indexes=(CREATED_AT_INDEX,))' in text
