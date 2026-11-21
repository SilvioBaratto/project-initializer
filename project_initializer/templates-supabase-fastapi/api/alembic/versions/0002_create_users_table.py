"""create profiles table

Revision ID: 0002_create_profiles
Revises: 0001_create_items
Create Date: 2026-06-09

Creates the ``profiles`` table of the Supabase variant, which extends Supabase's
own ``auth.users``. The file keeps the name of the base ``users`` migration on
purpose: template layers overwrite by path, so this file replaces it and a
Supabase project never gets a ``users`` table of its own. The downgrade copies the
rows into a backup table before dropping the table (see
``app.infrastructure.migration_safety``), so reverting never destroys data.

Column lengths are literals on purpose: a migration is a frozen snapshot of the
schema at this revision and must not follow later changes to the app constants.
``tests/integration/test_migrations.py`` catches drift against the ORM models.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.infrastructure.migration_safety import preserve_and_drop_table

revision: str = "0002_create_profiles"
down_revision: str | Sequence[str] | None = "0001_create_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID_LENGTH = 36
DISPLAY_NAME_LENGTH = 100
AVATAR_URL_LENGTH = 500
DISPLAY_NAME_INDEX = "idx_profiles_display_name"


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column(
            name,
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        )
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    """Create the profiles table and its display-name index."""
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(length=ID_LENGTH), nullable=False),
        sa.Column("display_name", sa.String(length=DISPLAY_NAME_LENGTH), nullable=True),
        sa.Column("avatar_url", sa.String(length=AVATAR_URL_LENGTH), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column(
            "preferences",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(DISPLAY_NAME_INDEX, "profiles", ["display_name"])


def downgrade() -> None:
    """Drop the profiles table after copying its rows into a backup table."""
    preserve_and_drop_table("profiles", indexes=(DISPLAY_NAME_INDEX,))
