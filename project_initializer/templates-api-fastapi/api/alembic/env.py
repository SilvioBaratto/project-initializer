"""Alembic environment.

The database URL comes from the application settings (``DIRECT_DATABASE_URL``,
falling back to ``DATABASE_URL``), so migrations and the application read the
same configuration and the connection arguments, TLS mode included, stay in one
place. Logging goes through the application's structured logger rather than
Alembic's ``fileConfig``, so migration output carries the same timestamps and
format as the rest of the service.

A caller that embeds the migrations, such as the test suite, sets
``config.attributes["embedded"]``: the environment and logging are then left as
the caller made them. It may also hand in an open connection through
``config.attributes["connection"]``.
"""

from typing import Any

from sqlalchemy import Connection, create_engine, pool

from alembic import context
from app.infrastructure.config import load_configuration

EMBEDDED_ATTRIBUTE = "embedded"
CONNECTION_ATTRIBUTE = "connection"

config = context.config
embedded = config.attributes.get(EMBEDDED_ATTRIBUTE, False)

# The settings singleton is built when its module is imported, so the project
# .env must reach the environment first.
if not embedded:
    load_configuration()

from app.infrastructure.database import build_connect_args  # noqa: E402
from app.infrastructure.migration_safety import (  # noqa: E402
    include_object,
    preserve_dropped_tables,
)
from app.infrastructure.orm.base import Base  # noqa: E402
from app.infrastructure.settings import settings  # noqa: E402
from app.infrastructure.structured_logging import configure_logging  # noqa: E402

if not embedded:
    configure_logging(settings.log_level, settings.log_format)

target_metadata = Base.metadata


def _configure(**options: Any) -> None:
    context.configure(
        target_metadata=target_metadata,
        include_object=include_object,
        process_revision_directives=preserve_dropped_tables,
        compare_type=True,
        compare_server_default=True,
        **options,
    )


def run_migrations_offline() -> None:
    """Emit the migration SQL without connecting to a database."""
    _configure(
        url=settings.migration_database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply the migrations on a live connection, in one transaction where supported."""
    injected = config.attributes.get(CONNECTION_ATTRIBUTE)
    if injected is not None:
        _run_migrations(injected)
        return
    url = settings.migration_database_url
    # Bound parameters stay out of error messages: a failed statement could
    # otherwise write row values into the migration log.
    engine = create_engine(
        url,
        poolclass=pool.NullPool,
        hide_parameters=True,
        connect_args=build_connect_args(url, settings),
    )
    with engine.connect() as connection:
        _run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
