"""Integration tests of the Supabase variant's migrations and ``profiles`` schema.

The base ``users`` migration must be replaced, not stacked: a Supabase project
keeps identities in Supabase Auth and owns only ``profiles``. Row level security
must cover every table, because the Data API serves ``public`` with the key the
single-page app ships. The behaviour every variant shares (a round trip, drift
against the ORM, backups) is tested once, in ``test_migrations.py``.
"""

import re

import pytest
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from alembic import command
from app.infrastructure.orm.user import ProfileRecord
from tests import migration_support
from tests.migration_support import (
    HEAD,
    alembic_config,
    backup_tables,
    migrate,
    offline_script,
    schema_tables,
)

pytestmark = pytest.mark.integration

# Binding the shared fixture to a name of this module is what makes pytest see it;
# a plain import would turn every test parameter into a redefined unused import.
migration_engine = migration_support.migration_engine

ITEMS_REVISION = "0001_create_items"
PROFILES_REVISION = "0002_create_profiles"
SECURITY_REVISION = "0003_enable_row_level_security"
SECURED_TABLES = ("items", "profiles", "alembic_version")
PROFILE_COLUMNS = {
    "id",
    "display_name",
    "avatar_url",
    "bio",
    "preferences",
    "created_at",
    "updated_at",
}
PROFILE_ID = "7c3a1f0e-5b9d-4e2a-8c61-2d4f9a0b1e33"
PREFERENCES = {"theme": "dark", "notifications": {"email": True}}


def position_of(pattern: str, script: str) -> int:
    """Index of the first match of ``pattern`` in ``script``; fails when absent."""
    match = re.search(pattern, script)
    assert match, f"{pattern!r} is not in the script"
    return match.start()


def test_when_the_revisions_are_listed_then_profiles_replace_users_in_one_chain():
    """when the migration scripts are read, one chain ends in the security revision.

    A stray base ``users`` migration would show up as a fourth revision.

    Validates alembic.versions.0002_create_users_table.
    """
    script = ScriptDirectory.from_config(alembic_config())

    revisions = [revision.revision for revision in script.walk_revisions()]

    assert revisions == [SECURITY_REVISION, PROFILES_REVISION, ITEMS_REVISION]
    assert script.get_heads() == [SECURITY_REVISION]


def test_when_upgraded_to_head_then_profiles_exist_and_users_do_not(migration_engine):
    """when the chain is applied, the schema holds items and profiles, never users.

    Validates alembic.versions.0002_create_users_table.upgrade().
    """
    migrate(migration_engine, command.upgrade, HEAD)

    assert schema_tables(migration_engine) == {"items", "profiles"}
    columns = {c["name"] for c in inspect(migration_engine).get_columns("profiles")}
    assert columns == PROFILE_COLUMNS


def test_when_upgraded_on_sqlite_then_the_security_revision_applies_without_effect(
    migration_engine,
):
    """when SQLite runs the chain, the security revision is recorded and changes nothing.

    Validates alembic.versions.0003_enable_row_level_security.upgrade().
    """
    migrate(migration_engine, command.upgrade, HEAD)

    with migration_engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    assert current == SECURITY_REVISION


def test_when_profiles_are_downgraded_then_their_rows_are_kept_in_a_backup_table(
    migration_engine,
):
    """when the profiles revision is reverted, rows survive in a backup table.

    Validates alembic.versions.0002_create_users_table.downgrade().
    """
    migrate(migration_engine, command.upgrade, HEAD)
    with migration_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO profiles (id, display_name) VALUES (:id, 'Jane')"),
            {"id": PROFILE_ID},
        )

    migrate(migration_engine, command.downgrade, ITEMS_REVISION)

    assert schema_tables(migration_engine) == {"items"}
    (backup,) = [n for n in backup_tables(migration_engine) if n.startswith("profiles")]
    with migration_engine.connect() as connection:
        rows = connection.execute(text(f"SELECT id, display_name FROM {backup}")).all()
    assert [tuple(row) for row in rows] == [(PROFILE_ID, "Jane")]


def test_when_offline_then_the_upgrade_sql_creates_profiles_with_binary_json():
    """when the upgrade SQL is rendered for PostgreSQL, it creates profiles as JSONB.

    Validates alembic.versions.0002_create_users_table.upgrade().
    """
    script = offline_script(HEAD)

    assert "CREATE TABLE profiles" in script
    assert "CREATE TABLE users" not in script
    assert "preferences JSONB" in script


def test_when_offline_then_the_upgrade_sql_enables_row_level_security_on_every_table():
    """when the upgrade SQL is rendered, every table is secured after it exists.

    Validates alembic.versions.0003_enable_row_level_security.upgrade().
    """
    script = offline_script(HEAD)

    for table in SECURED_TABLES:
        enable = position_of(rf"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;", script)
        assert enable > position_of(rf"CREATE TABLE {table} ", script)


def test_when_offline_then_the_upgrade_sql_adds_no_policy_and_does_not_force_security():
    """when the upgrade SQL is rendered, the owner role keeps working.

    A policy would open a table to the Data API, and ``FORCE`` would lock out the
    API's own connection, which is the table owner.

    Validates alembic.versions.0003_enable_row_level_security.upgrade().
    """
    script = offline_script(HEAD)

    assert "CREATE POLICY" not in script
    assert "FORCE ROW LEVEL SECURITY" not in script


def test_when_offline_then_the_downgrade_sql_disables_row_level_security_first():
    """when the downgrade SQL is rendered, security goes off before any table is dropped.

    Validates alembic.versions.0003_enable_row_level_security.downgrade().
    """
    script = offline_script(f"{HEAD}:base", downgrade=True)

    first_drop = position_of(r"DROP TABLE ", script)
    for table in SECURED_TABLES:
        disable = position_of(
            rf"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;", script
        )
        assert disable < first_drop


def test_when_offline_then_the_profiles_backup_goes_to_the_backup_schema():
    """when the downgrade SQL is rendered, profiles are copied out of ``public`` first.

    Validates alembic.versions.0002_create_users_table.downgrade().
    """
    script = offline_script(f"{HEAD}:base", downgrade=True)

    copy = position_of(
        r"CREATE TABLE migration_backup\.profiles__rollback_\d{20} "
        r"AS SELECT \* FROM profiles;",
        script,
    )
    assert copy < position_of(r"DROP TABLE profiles;", script)


def test_when_the_preferences_type_is_compiled_then_it_is_jsonb_only_on_postgresql():
    """when the column type is rendered, PostgreSQL gets JSONB and SQLite plain JSON.

    Validates app.infrastructure.orm.user.ProfileRecord.
    """
    column_type = ProfileRecord.__table__.c.preferences.type

    assert column_type.compile(dialect=postgresql.dialect()) == "JSONB"
    assert column_type.compile(dialect=sqlite.dialect()) == "JSON"


def test_when_preferences_are_stored_then_they_round_trip_on_sqlite(
    db_session: Session,
):
    """when a profile with nested preferences is saved, it is read back unchanged.

    Validates app.infrastructure.orm.user.ProfileRecord.
    """
    db_session.add(ProfileRecord(id=PROFILE_ID, preferences=PREFERENCES))
    db_session.flush()
    db_session.expire_all()

    stored = db_session.get(ProfileRecord, PROFILE_ID)

    assert stored is not None
    assert stored.preferences == PREFERENCES
    assert stored.created_at is not None


def test_when_a_profile_is_printed_then_only_its_id_is_shown():
    """when a profile is rendered for logs, personal fields are left out.

    Validates app.infrastructure.orm.user.ProfileRecord.__repr__().
    """
    profile = ProfileRecord(id=PROFILE_ID, display_name="Jane Doe", bio="Private")

    assert repr(profile) == f"<ProfileRecord id={PROFILE_ID}>"
