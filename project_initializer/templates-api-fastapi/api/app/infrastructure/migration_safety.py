"""Helpers that make destructive migration steps recoverable.

A downgrade that drops a table or a column would destroy its rows. The helpers
here copy them into a backup table first. On PostgreSQL the backups live in the
``migration_backup`` schema, which the Supabase Data API does not expose and no
application role can read by default; a backup in ``public`` would hold the rows
of a table without the access rules of the original. SQLite has no schemas to
speak of, so its backups sit beside the table under a distinguishing name.

Backup tables are not part of the ORM schema, so Alembic autogenerate must skip
them; ``include_object`` does that. A drafted downgrade that would drop a table
is rewritten to ``preserve_and_drop_table`` by ``preserve_dropped_tables``.
"""

import json
import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic.autogenerate import renderers
from alembic.operations import ops

from alembic import op

logger = logging.getLogger(__name__)

BACKUP_SCHEMA = "migration_backup"
BACKUP_TABLE_INFIX = "__rollback_"
# Microseconds keep two downgrades inside one second apart: a database that is
# migrated down, up and down again quickly must not collide on the backup name.
BACKUP_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S%f"
BACKUP_TIMESTAMP_DIGITS = 20
POSTGRESQL_DIALECT = "postgresql"
PRESERVE_IMPORT = (
    "from app.infrastructure.migration_safety import preserve_and_drop_table"
)

_BACKUP_NAME_PATTERN = re.compile(
    rf"{re.escape(BACKUP_TABLE_INFIX)}\d{{{BACKUP_TIMESTAMP_DIGITS}}}$"
)


def backup_table_name(
    table: str, *, now: datetime, max_length: int | None = None
) -> str:
    """Name the backup table for a dropped table.

    Args:
        table: Name of the table about to be dropped.
        now: Moment of the downgrade; its microsecond resolution keeps the names
            of repeated downgrades apart.
        max_length: Longest identifier the database accepts. PostgreSQL silently
            truncates a longer name, which would make two backups collide.

    Returns:
        ``<table>__rollback_<YYYYmmddHHMMSSffffff>``.

    Raises:
        ValueError: The name is longer than ``max_length``; shorten the table name.
    """
    name = f"{table}{BACKUP_TABLE_INFIX}{now.strftime(BACKUP_TIMESTAMP_FORMAT)}"
    if max_length is not None and len(name) > max_length:
        raise ValueError(
            f"Backup table name {name!r} has {len(name)} characters but the "
            f"database allows {max_length}: table {table!r} is too long to back up"
        )
    return name


def backup_schema_for(dialect_name: str) -> str | None:
    """Return the schema that holds backups on a database, or None for the default.

    Args:
        dialect_name: SQLAlchemy dialect name, such as ``postgresql`` or ``sqlite``.

    Returns:
        ``migration_backup`` on PostgreSQL; None elsewhere, where backups are
        created next to the table they copy.
    """
    return BACKUP_SCHEMA if dialect_name == POSTGRESQL_DIALECT else None


def is_backup_table(name: str, schema: str | None = None) -> bool:
    """Tell whether a table is a backup made by the helpers in this module.

    Args:
        name: Table name.
        schema: Schema the table lives in, when known.

    Returns:
        True for any table in the backup schema and for a table whose name ends
        in the backup suffix.
    """
    return schema == BACKUP_SCHEMA or _BACKUP_NAME_PATTERN.search(name) is not None


def include_object(
    obj: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object,
) -> bool:
    """Alembic ``include_object`` hook that keeps backup tables out of comparisons.

    Args:
        obj: Schema object under comparison.
        name: Its name.
        type_: Kind of object, such as ``table`` or ``index``.
        reflected: Whether the object was reflected from the database.
        compare_to: The matching object on the other side, when there is one.

    Returns:
        False for a backup table, so autogenerate neither reports it as
        missing from the models nor proposes to drop it.
    """
    if type_ != "table" or name is None:
        return True
    return not is_backup_table(name, getattr(obj, "schema", None))


def _create_backup(table: str, columns: Sequence[str] | None) -> str:
    """Copy a table, or some of its columns, into a new backup table.

    ``CREATE TABLE ... AS SELECT`` carries the rows but no constraints or
    indexes, so re-applying the upgrade creates the originals again without a
    name collision. Identifiers are quoted by the dialect and come from the
    migration source, never from input.

    Returns:
        The backup table name, qualified with its schema where there is one.
    """
    dialect = op.get_context().dialect
    preparer = dialect.identifier_preparer
    backup = backup_table_name(
        table, now=datetime.now(UTC), max_length=dialect.max_identifier_length
    )
    target = preparer.quote(backup)
    schema = backup_schema_for(dialect.name)
    if schema is not None:
        quoted_schema = preparer.quote_schema(schema)
        # PostgreSQL grants a new schema to no role but its creator, so the
        # backups stay unreadable to the application and Data API roles.
        op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}"))
        target = f"{quoted_schema}.{target}"
    selected = "*" if columns is None else ", ".join(map(preparer.quote, columns))
    source = preparer.quote(table)
    op.execute(sa.text(f"CREATE TABLE {target} AS SELECT {selected} FROM {source}"))
    return target


def _log_preserved(table: str, backup: str) -> None:
    planned = op.get_context().as_sql
    event = "migration.preserve_planned" if planned else "migration.preserved"
    logger.warning("%s table=%s backup=%s", event, table, backup)


def preserve_and_drop_table(table: str, *, indexes: Sequence[str] = ()) -> str:
    """Copy a table into a backup table, then drop its indexes and the table.

    Args:
        table: Name of the table to drop.
        indexes: Names of the indexes on ``table`` to drop before the table.

    Returns:
        The backup table name, qualified with its schema on PostgreSQL. In
        offline mode (``--sql``) it is the name the emitted script uses.

    Raises:
        ValueError: The backup name would exceed the database's identifier limit.
    """
    backup = _create_backup(table, None)
    for index in indexes:
        op.drop_index(index, table_name=table)
    op.drop_table(table)
    _log_preserved(table, backup)
    return backup


def preserve_and_drop_column(
    table: str, column: str, *, key_columns: Sequence[str]
) -> str:
    """Copy one column into a backup table, then drop it from its table.

    Args:
        table: Table that owns the column.
        column: Name of the column to drop.
        key_columns: Columns that identify a row, normally the primary key, so a
            backed-up value can be matched to its row again.

    Returns:
        The backup table name, qualified with its schema on PostgreSQL.

    Raises:
        ValueError: The backup name would exceed the database's identifier limit.
    """
    backup = _create_backup(table, [*key_columns, column])
    op.drop_column(table, column)
    _log_preserved(table, backup)
    return backup


class PreserveAndDropTableOp(ops.MigrateOperation):
    """Draft-time stand-in for a dropped table in a generated downgrade.

    It only renders, as a call to ``preserve_and_drop_table``; the migration file
    that results runs the plain function.
    """

    def __init__(self, table_name: str) -> None:
        self.table_name = table_name


@renderers.dispatch_for(PreserveAndDropTableOp)
def _render_preserve_and_drop_table(autogen_context: Any, operation: Any) -> str:
    autogen_context.imports.add(PRESERVE_IMPORT)
    return f"preserve_and_drop_table({json.dumps(operation.table_name)})"


def preserve_dropped_tables(context: Any, revision: Any, directives: list[Any]) -> None:
    """Alembic ``process_revision_directives`` hook for autogenerate.

    Rewrites every ``DropTableOp`` the draft puts in a downgrade, so a table the
    upgrade creates is never dropped without a backup. A drop that names a schema
    is left alone, and the migration test suite then flags it.

    Args:
        context: Migration context of the running command (unused).
        revision: Revision being generated (unused).
        directives: One ``MigrationScript`` per revision being generated; its
            downgrade operations are changed in place.
    """
    for script in directives:
        for downgrade_ops in script.downgrade_ops_list:
            downgrade_ops.ops[:] = [
                PreserveAndDropTableOp(operation.table_name)
                if isinstance(operation, ops.DropTableOp) and operation.schema is None
                else operation
                for operation in downgrade_ops.ops
            ]
