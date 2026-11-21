"""Integration tests for the Alembic migrations, run on in-memory SQLite.

They apply the chain forwards and backwards through the real ``env.py`` and
compare the result with the ORM metadata, so a model change without a matching
migration fails here. The migrations use only portable DDL, so SQLite exercises
the same operations PostgreSQL runs; what only PostgreSQL does (the backup
schema, row level security) is asserted on the SQL that an offline run renders.
"""

import io
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import (
    Column,
    Connection,
    Engine,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
    text,
)

from alembic import command
from app.infrastructure.migration_safety import (
    BACKUP_SCHEMA,
    backup_table_name,
    include_object,
    is_backup_table,
    preserve_and_drop_column,
    preserve_and_drop_table,
)
from app.infrastructure.orm.base import Base
from app.infrastructure.settings import settings
from tests import migration_support
from tests.migration_support import (
    BASE,
    HEAD,
    VERSIONS_DIR,
    alembic_config,
    backup_tables,
    destructive_calls_in_downgrade,
    migrate,
    offline_script,
    schema_diff,
    schema_tables,
)

pytestmark = pytest.mark.integration

# Binding the shared fixture to a name of this module is what makes pytest see it;
# a plain import would turn every test parameter into a redefined unused import.
migration_engine = migration_support.migration_engine

MOMENT = datetime(2026, 1, 2, 3, 4, 5, 678901, tzinfo=UTC)
REVISION_FILE_PATTERN = re.compile(r"^\d{4}_[a-z0-9_]+\.py$")
# alembic_version.version_num is VARCHAR(32).
REVISION_ID_MAX_LENGTH = 32
POSTGRESQL_IDENTIFIER_LIMIT = 63
CYCLES_WITHIN_A_MOMENT = 2
# "__rollback_" plus YYYYmmddHHMMSS and six microsecond digits.
BACKUP_SUFFIX_LENGTH = len("__rollback_") + 14 + 6
GENERATED_REVISION_ID = "0099_add_hook_widgets"


def postgresql_context() -> tuple[MigrationContext, io.StringIO]:
    """A migration context that renders PostgreSQL statements into a buffer."""
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer}
    )
    return context, buffer


def test_when_upgraded_to_head_then_exactly_the_orm_tables_exist(migration_engine):
    """Validates alembic.env.run_migrations_online()."""
    migrate(migration_engine, command.upgrade, HEAD)

    expected = {table.name for table in Base.metadata.sorted_tables}
    assert schema_tables(migration_engine) == expected


def test_when_no_connection_is_injected_then_env_opens_its_own_engine_from_the_settings(
    tmp_path,
):
    """Validates alembic.env.run_migrations_online()."""
    url = f"sqlite:///{tmp_path / 'migrated.db'}"

    with (
        patch.object(settings, "database_migration_url", url),
        patch.object(settings, "database_url", url),
    ):
        command.upgrade(alembic_config(), HEAD)

    engine = create_engine(url)
    assert "items" in inspect(engine).get_table_names()
    engine.dispose()


def test_when_upgraded_to_head_then_the_schema_matches_the_orm_models(migration_engine):
    """Validates alembic.env.run_migrations_online()."""
    migrate(migration_engine, command.upgrade, HEAD)

    assert schema_diff(migration_engine) == []


def test_when_a_row_omits_defaulted_columns_then_the_database_fills_them(
    migration_engine,
):
    """Validates alembic.versions.0001_create_items_table.upgrade()."""
    migrate(migration_engine, command.upgrade, HEAD)

    with migration_engine.begin() as connection:
        connection.execute(text("INSERT INTO items (id, name) VALUES ('a', 'x')"))
        is_active, created_at, updated_at = connection.execute(
            text("SELECT is_active, created_at, updated_at FROM items")
        ).one()

    assert bool(is_active) is True
    assert created_at is not None
    assert updated_at is not None


def test_when_upgraded_to_head_then_items_are_indexed_by_creation_time(
    migration_engine,
):
    """Validates alembic.versions.0001_create_items_table.upgrade()."""
    migrate(migration_engine, command.upgrade, HEAD)

    indexes = inspect(migration_engine).get_indexes("items")

    assert [index["column_names"] for index in indexes] == [["created_at"]]


def test_when_downgraded_to_base_then_only_backup_tables_remain(migration_engine):
    """Validates alembic.versions.0001_create_items_table.downgrade()."""
    migrate(migration_engine, command.upgrade, HEAD)

    migrate(migration_engine, command.downgrade, BASE)

    assert schema_tables(migration_engine) == set()
    assert backup_tables(migration_engine)


def test_when_downgraded_then_the_rows_are_kept_in_a_backup_table(
    migration_engine, caplog
):
    """Validates app.infrastructure.migration_safety.preserve_and_drop_table()."""
    migrate(migration_engine, command.upgrade, HEAD)
    with migration_engine.begin() as connection:
        connection.execute(text("INSERT INTO items (id, name) VALUES ('keep', 'Kept')"))

    with caplog.at_level(logging.WARNING, logger="app.infrastructure.migration_safety"):
        migrate(migration_engine, command.downgrade, BASE)

    (backup,) = [n for n in backup_tables(migration_engine) if n.startswith("items")]
    with migration_engine.connect() as connection:
        rows = connection.execute(text(f"SELECT id, name FROM {backup}")).all()
    assert [tuple(row) for row in rows] == [("keep", "Kept")]
    assert f"migration.preserved table=items backup={backup}" in caplog.text


def test_when_the_chain_is_cycled_twice_in_a_moment_then_each_downgrade_keeps_a_backup(
    migration_engine,
):
    """Validates app.infrastructure.migration_safety.backup_table_name()."""
    for _ in range(CYCLES_WITHIN_A_MOMENT):
        migrate(migration_engine, command.upgrade, HEAD)
        migrate(migration_engine, command.downgrade, BASE)

    item_backups = [n for n in backup_tables(migration_engine) if n.startswith("items")]
    assert len(item_backups) == CYCLES_WITHIN_A_MOMENT


def test_when_upgraded_again_after_a_downgrade_then_the_schema_matches_the_models(
    migration_engine,
):
    """Validates alembic.env.run_migrations_online()."""
    migrate(migration_engine, command.upgrade, HEAD)
    migrate(migration_engine, command.downgrade, BASE)

    migrate(migration_engine, command.upgrade, HEAD)

    expected = {table.name for table in Base.metadata.sorted_tables}
    assert schema_tables(migration_engine) == expected
    assert schema_diff(migration_engine) == []


def test_when_offline_then_the_upgrade_sql_creates_the_tables():
    """Validates alembic.env.run_migrations_offline()."""
    script = offline_script(HEAD)

    for table in Base.metadata.sorted_tables:
        assert f"CREATE TABLE {table.name}" in script
    assert "CREATE INDEX idx_items_created_at ON items (created_at)" in script


def test_when_offline_then_the_downgrade_sql_copies_rows_into_the_backup_schema_first():
    """Validates app.infrastructure.migration_safety.preserve_and_drop_table()."""
    script = offline_script(f"{HEAD}:{BASE}", downgrade=True)

    schema = re.search(rf"CREATE SCHEMA IF NOT EXISTS {BACKUP_SCHEMA};", script)
    copy = re.search(
        rf"CREATE TABLE {BACKUP_SCHEMA}\.items__rollback_\d{{20}} "
        r"AS SELECT \* FROM items;",
        script,
    )
    drop = re.search(r"DROP TABLE items;", script)
    assert schema and copy and drop
    assert schema.start() < copy.start() < drop.start()


def test_when_offline_then_the_downgrade_logs_the_backup_as_planned(caplog):
    """Validates app.infrastructure.migration_safety.preserve_and_drop_table()."""
    with caplog.at_level(logging.WARNING, logger="app.infrastructure.migration_safety"):
        offline_script(f"{HEAD}:{BASE}", downgrade=True)

    assert "migration.preserve_planned table=items" in caplog.text
    assert "migration.preserved " not in caplog.text


def test_when_a_backup_name_is_built_then_it_carries_the_table_and_a_timestamp():
    """Validates app.infrastructure.migration_safety.backup_table_name()."""
    name = backup_table_name("items", now=MOMENT)

    assert name == "items__rollback_20260102030405678901"


def test_when_two_moments_share_a_second_then_their_backup_names_differ():
    """Validates app.infrastructure.migration_safety.backup_table_name()."""
    later = MOMENT.replace(microsecond=MOMENT.microsecond + 1)

    assert backup_table_name("items", now=MOMENT) != backup_table_name(
        "items", now=later
    )


def test_when_a_backup_name_fits_the_limit_exactly_then_it_is_accepted():
    """Validates app.infrastructure.migration_safety.backup_table_name()."""
    table = "t" * (POSTGRESQL_IDENTIFIER_LIMIT - BACKUP_SUFFIX_LENGTH)

    name = backup_table_name(table, now=MOMENT, max_length=POSTGRESQL_IDENTIFIER_LIMIT)

    assert len(name) == POSTGRESQL_IDENTIFIER_LIMIT


def test_when_a_backup_name_exceeds_the_limit_then_it_is_refused():
    """Validates app.infrastructure.migration_safety.backup_table_name()."""
    table = "t" * (POSTGRESQL_IDENTIFIER_LIMIT - BACKUP_SUFFIX_LENGTH + 1)

    with pytest.raises(ValueError, match="too long to back up"):
        backup_table_name(table, now=MOMENT, max_length=POSTGRESQL_IDENTIFIER_LIMIT)


@pytest.mark.parametrize(
    ("name", "schema", "expected"),
    [
        ("items__rollback_20260102030405678901", None, True),
        ("items", BACKUP_SCHEMA, True),
        ("items", None, False),
        ("items", "public", False),
        ("items__rollback_notes", None, False),
        ("items__rollback_2026", None, False),
    ],
)
def test_when_a_table_is_classified_then_only_backups_are_recognised(
    name, schema, expected
):
    """Validates app.infrastructure.migration_safety.is_backup_table()."""
    assert is_backup_table(name, schema) is expected


def test_when_comparing_schemas_then_backup_tables_are_excluded_but_others_are_not():
    """Validates app.infrastructure.migration_safety.include_object()."""
    backup = backup_table_name("items", now=MOMENT)
    in_backup_schema = Table("items", MetaData(), schema=BACKUP_SCHEMA)
    plain = Table("items", MetaData())

    assert not include_object(None, backup, "table", True, None)
    assert not include_object(in_backup_schema, "items", "table", True, None)
    assert include_object(plain, "items", "table", True, None)
    assert include_object(None, None, "column", True, None)
    assert include_object(None, backup, "index", True, None)


def test_when_the_versions_are_listed_then_each_file_is_numbered_and_named_by_slug():
    """Validates alembic.ini file_template."""
    names = [path.name for path in VERSIONS_DIR.glob("*.py")]

    assert names
    assert [n for n in names if not REVISION_FILE_PATTERN.match(n)] == []


def test_when_the_chain_is_walked_then_it_is_linear_with_ids_that_fit_the_version_table():
    """Validates alembic.script.ScriptDirectory."""
    script = ScriptDirectory.from_config(alembic_config())

    revisions = list(script.walk_revisions())

    assert len(script.get_heads()) == 1
    assert [
        r.revision for r in revisions if r.is_branch_point or r.is_merge_point
    ] == []
    assert [
        r.revision for r in revisions if len(r.revision) > REVISION_ID_MAX_LENGTH
    ] == []


def test_when_a_downgrade_drops_directly_then_the_check_reports_it():
    """Validates tests.migration_support.destructive_calls_in_downgrade()."""
    source = (
        "def upgrade():\n"
        "    op.drop_table('kept_in_upgrade')\n"
        "def downgrade():\n"
        "    op.drop_table('items')\n"
        "    op.drop_column('items', 'note')\n"
        "    preserve_and_drop_table('users')\n"
    )

    assert destructive_calls_in_downgrade(source) == [
        "drop_table (line 4)",
        "drop_column (line 5)",
    ]


def test_when_every_migration_is_read_then_no_downgrade_drops_directly():
    """Validates alembic.versions.downgrade()."""
    offenders = {
        path.name: destructive_calls_in_downgrade(path.read_text(encoding="utf-8"))
        for path in sorted(VERSIONS_DIR.glob("*.py"))
    }

    assert {name: calls for name, calls in offenders.items() if calls} == {}


def test_when_a_column_is_preserved_then_its_values_survive_beside_the_row_keys(
    migration_engine,
):
    """Validates app.infrastructure.migration_safety.preserve_and_drop_column()."""
    with migration_engine.begin() as connection:
        connection.execute(text("CREATE TABLE things (id TEXT PRIMARY KEY, note TEXT)"))
        connection.execute(text("INSERT INTO things VALUES ('a', 'kept')"))
        with Operations.context(MigrationContext.configure(connection)):
            backup = preserve_and_drop_column("things", "note", key_columns=["id"])

    assert [c["name"] for c in inspect(migration_engine).get_columns("things")] == [
        "id"
    ]
    with migration_engine.connect() as connection:
        rows = connection.execute(text(f"SELECT id, note FROM {backup}")).all()
    assert [tuple(row) for row in rows] == [("a", "kept")]


def test_when_a_table_is_preserved_on_postgresql_then_the_backup_goes_to_its_schema():
    """Validates app.infrastructure.migration_safety.preserve_and_drop_table()."""
    context, buffer = postgresql_context()

    with Operations.context(context):
        backup = preserve_and_drop_table("items")

    assert backup.startswith(f"{BACKUP_SCHEMA}.items__rollback_")
    assert f"CREATE TABLE {backup} AS SELECT * FROM items;" in buffer.getvalue()


def test_when_a_table_name_is_too_long_to_back_up_then_nothing_is_emitted():
    """Validates app.infrastructure.migration_safety.preserve_and_drop_table()."""
    context, buffer = postgresql_context()
    table = "t" * (POSTGRESQL_IDENTIFIER_LIMIT - BACKUP_SUFFIX_LENGTH + 1)

    with Operations.context(context), pytest.raises(ValueError, match="too long"):
        preserve_and_drop_table(table)

    assert buffer.getvalue() == ""


@pytest.fixture
def widget_model():
    """A model table the migrations do not create yet, so autogenerate adds it."""
    table = Table(
        "hook_widgets",
        Base.metadata,
        Column("id", String(36), primary_key=True),
        Column("label", String(40)),
    )
    yield table
    Base.metadata.remove(table)


def config_with_versions_in(connection: Connection, directory: Path) -> Config:
    """The project config, with ``directory`` added to the revision locations."""
    config = alembic_config(connection)
    locations = os.pathsep.join([str(VERSIONS_DIR), str(directory)])
    config.set_main_option("version_locations", locations)
    return config


def autogenerate_widget_revision(engine: Engine, directory: Path) -> str:
    """Draft a revision for ``widget_model`` into ``directory``; return its source."""
    with engine.begin() as connection:
        command.revision(
            config_with_versions_in(connection, directory),
            message="add hook widgets",
            autogenerate=True,
            rev_id=GENERATED_REVISION_ID,
            version_path=str(directory),
        )
    return (directory / f"{GENERATED_REVISION_ID}.py").read_text(encoding="utf-8")


def test_when_a_revision_is_autogenerated_then_its_downgrade_preserves_the_table(
    migration_engine, widget_model, tmp_path
):
    """Validates app.infrastructure.migration_safety.preserve_dropped_tables()."""
    migrate(migration_engine, command.upgrade, HEAD)

    source = autogenerate_widget_revision(migration_engine, tmp_path)

    assert 'preserve_and_drop_table("hook_widgets")' in source
    assert (
        "from app.infrastructure.migration_safety import preserve_and_drop_table"
        in source
    )
    assert "op.drop_table" not in source
    assert "commands auto generated" not in source
    assert destructive_calls_in_downgrade(source) == []


def test_when_an_autogenerated_revision_is_applied_then_it_runs_and_rolls_back_safely(
    migration_engine, widget_model, tmp_path
):
    """Validates alembic.script.py.mako."""
    migrate(migration_engine, command.upgrade, HEAD)
    autogenerate_widget_revision(migration_engine, tmp_path)

    with migration_engine.begin() as connection:
        config = config_with_versions_in(connection, tmp_path)
        command.upgrade(config, HEAD)
        connection.execute(sa.text("INSERT INTO hook_widgets (id) VALUES ('w1')"))
        command.downgrade(config, "-1")

    (backup,) = [n for n in backup_tables(migration_engine) if "hook_widgets" in n]
    assert "hook_widgets" not in schema_tables(migration_engine)
    with migration_engine.connect() as connection:
        assert connection.execute(text(f"SELECT id FROM {backup}")).scalar_one() == "w1"
