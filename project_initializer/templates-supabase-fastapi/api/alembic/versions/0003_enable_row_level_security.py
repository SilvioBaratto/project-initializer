"""enable row level security

Revision ID: 0003_enable_row_level_security
Revises: 0002_create_profiles
Create Date: 2026-11-21

Supabase serves every table of the ``public`` schema through its Data API, and the
single-page app ships the publishable key. Without row level security that key
could read and write ``items`` and ``profiles``, and read the migration bookkeeping
in ``alembic_version``. With security enabled and no policy, the ``anon`` and
``authenticated`` roles can do nothing on those tables.

No policy is added and security is not forced: the API connects as the table owner,
which row level security does not apply to, and it is the only intended client of
these tables. A table that the Data API should serve gets its own policy in a
later migration. Backups made by a downgrade live in the ``migration_backup``
schema, which the Data API does not expose.

Only PostgreSQL has row level security, so the migration does nothing on the SQLite
database the tests use.
"""

from collections.abc import Sequence

from alembic import op
from app.infrastructure.migration_safety import POSTGRESQL_DIALECT

revision: str = "0003_enable_row_level_security"
down_revision: str | Sequence[str] | None = "0002_create_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SECURED_TABLES = ("items", "profiles", "alembic_version")


def _alter_row_level_security(action: str) -> None:
    dialect = op.get_context().dialect
    if dialect.name != POSTGRESQL_DIALECT:
        return
    quote = dialect.identifier_preparer.quote
    for table in SECURED_TABLES:
        op.execute(f"ALTER TABLE {quote(table)} {action} ROW LEVEL SECURITY")


def upgrade() -> None:
    """Enable row level security on every table, leaving no policy."""
    _alter_row_level_security("ENABLE")


def downgrade() -> None:
    """Disable row level security again, which exposes the tables to the Data API."""
    _alter_row_level_security("DISABLE")
