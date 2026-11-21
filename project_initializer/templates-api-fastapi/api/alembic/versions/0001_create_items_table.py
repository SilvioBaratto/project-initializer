"""create items table

Revision ID: 0001_create_items
Revises:
Create Date: 2026-06-08

Creates the ``items`` table and the index that serves its newest-first listing.
The downgrade copies the rows into a backup table before dropping it (see
``app.infrastructure.migration_safety``), so reverting never destroys data.

Column lengths are literals on purpose: a migration is a frozen snapshot of the
schema at this revision and must not follow later changes to the app constants.
``tests/integration/test_migrations.py`` catches drift against the ORM models.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.infrastructure.migration_safety import preserve_and_drop_table

# revision identifiers, used by Alembic.
revision: str = "0001_create_items"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID_LENGTH = 36
NAME_LENGTH = 100
DESCRIPTION_LENGTH = 500
CREATED_AT_INDEX = "idx_items_created_at"


def upgrade() -> None:
    """Create the items table and its creation-time index."""
    op.create_table(
        "items",
        sa.Column("id", sa.String(length=ID_LENGTH), nullable=False),
        sa.Column("name", sa.String(length=NAME_LENGTH), nullable=False),
        sa.Column("description", sa.String(length=DESCRIPTION_LENGTH), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(CREATED_AT_INDEX, "items", ["created_at"])


def downgrade() -> None:
    """Drop the items table after copying its rows into a backup table."""
    preserve_and_drop_table("items", indexes=(CREATED_AT_INDEX,))
