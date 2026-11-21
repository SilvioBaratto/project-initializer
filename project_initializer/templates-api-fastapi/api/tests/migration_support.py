"""Helpers shared by the migration test suites of every variant.

They live here, not in a test module, so a variant's own migration tests import
them without importing another test module and without copying fixtures. A test
module imports the fixtures it uses, which is what makes pytest see them.
"""

import ast
import io
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Connection, Engine, create_engine, inspect
from sqlalchemy.pool import StaticPool

from alembic import command
from app.infrastructure.migration_safety import (
    backup_schema_for,
    include_object,
    is_backup_table,
)
from app.infrastructure.orm.base import Base
from app.infrastructure.settings import DEFAULT_DATABASE_URL, settings

API_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = API_DIR / "alembic.ini"
VERSIONS_DIR = API_DIR / "alembic" / "versions"
VERSION_TABLE = "alembic_version"
HEAD = "head"
BASE = "base"
# The attribute env.py reads to leave the environment and logging to the caller.
EMBEDDED_ATTRIBUTE = "embedded"
CONNECTION_ATTRIBUTE = "connection"
DESTRUCTIVE_OPERATIONS = frozenset({"drop_table", "drop_column"})


@pytest.fixture
def migration_engine() -> Iterator[Engine]:
    """An empty in-memory database shared by every connection."""
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    yield engine
    engine.dispose()


def alembic_config(connection: Connection | None = None) -> Config:
    """Build the project's Alembic config, optionally bound to an open connection."""
    config = Config(str(ALEMBIC_INI))
    config.attributes[EMBEDDED_ATTRIBUTE] = True
    if connection is not None:
        config.attributes[CONNECTION_ATTRIBUTE] = connection
    return config


def migrate(
    engine: Engine, action: Callable[[Config, str], None], revision: str
) -> None:
    """Run ``upgrade`` or ``downgrade`` to ``revision`` in one transaction."""
    with engine.begin() as connection:
        action(alembic_config(connection), revision)


def offline_script(revision_range: str, *, downgrade: bool = False) -> str:
    """Render the SQL of an offline (``--sql``) run for a revision range.

    Args:
        revision_range: Target revision, or ``<from>:<to>`` for a downgrade.
        downgrade: Render a downgrade instead of an upgrade.

    Returns:
        The script text, always in the PostgreSQL dialect: the database named in
        a developer's ``.env`` must not change what these tests assert.
    """
    config = alembic_config()
    config.output_buffer = io.StringIO()
    action = command.downgrade if downgrade else command.upgrade
    with (
        patch.object(settings, "database_migration_url", None),
        patch.object(settings, "database_url", DEFAULT_DATABASE_URL),
    ):
        action(config, revision_range, sql=True)
    return config.output_buffer.getvalue()


def schema_tables(engine: Engine) -> set[str]:
    """Names of the tables the migrations own, without bookkeeping or backups."""
    names = set(inspect(engine).get_table_names())
    return {n for n in names if n != VERSION_TABLE and not is_backup_table(n)}


def backup_tables(engine: Engine) -> list[str]:
    """Names of the backup tables a downgrade left behind, wherever they live."""
    schema = backup_schema_for(engine.dialect.name)
    names = inspect(engine).get_table_names(schema=schema)
    return sorted(n for n in names if is_backup_table(n, schema))


def schema_diff(engine: Engine) -> list:
    """Differences between the migrated database and the ORM metadata.

    Server defaults are compared too, so a default declared on a model without a
    migration (or the reverse) fails the suite.
    """
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                "compare_type": True,
                "compare_server_default": True,
                "include_object": include_object,
            },
        )
        return compare_metadata(context, Base.metadata)


def destructive_calls_in_downgrade(source: str) -> list[str]:
    """Find direct ``op.drop_table`` and ``op.drop_column`` calls in ``downgrade()``.

    Args:
        source: Python source of one migration file.

    Returns:
        One ``<operation> (line N)`` entry per offending call. Dropping through
        ``preserve_and_drop_table`` or ``preserve_and_drop_column`` is not
        reported, because those copy the data aside first.
    """
    found: list[str] = []
    for node in ast.parse(source).body:
        if not (isinstance(node, ast.FunctionDef) and node.name == "downgrade"):
            continue
        for call in ast.walk(node):
            if entry := _destructive_call_entry(call):
                found.append(entry)
    return found


def _destructive_call_entry(node: ast.AST) -> str | None:
    """Report ``node`` as ``<operation> (line N)`` when it is a destructive ``op`` call."""
    if not isinstance(node, ast.Call):
        return None
    target = node.func
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "op"
        and target.attr in DESTRUCTIVE_OPERATIONS
    ):
        return f"{target.attr} (line {node.lineno})"
    return None
