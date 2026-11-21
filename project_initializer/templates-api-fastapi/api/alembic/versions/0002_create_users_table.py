"""create users table

Revision ID: 0002_create_users
Revises: 0001_create_items
Create Date: 2026-06-09

Creates the ``users`` table used by the token authentication variant. The
downgrade copies the accounts into a backup table before dropping it (see
``app.infrastructure.migration_safety``), so reverting never destroys data.

Column lengths are literals on purpose: a migration is a frozen snapshot of the
schema at this revision and must not follow later changes to the app constants.
``tests/integration/test_migrations.py`` catches drift against the ORM models.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.infrastructure.migration_safety import preserve_and_drop_table

revision: str = "0002_create_users"
down_revision: str | Sequence[str] | None = "0001_create_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID_LENGTH = 36
EMAIL_LENGTH = 255
USERNAME_LENGTH = 50
PASSWORD_HASH_LENGTH = 255
PERSON_NAME_LENGTH = 100
ACTIVE_INDEX = "idx_users_is_active"


def _account_columns() -> list[sa.Column]:
    return [
        sa.Column("email", sa.String(length=EMAIL_LENGTH), nullable=False),
        sa.Column("username", sa.String(length=USERNAME_LENGTH), nullable=True),
        sa.Column(
            "password_hash", sa.String(length=PASSWORD_HASH_LENGTH), nullable=True
        ),
        sa.Column("first_name", sa.String(length=PERSON_NAME_LENGTH), nullable=True),
        sa.Column("last_name", sa.String(length=PERSON_NAME_LENGTH), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "is_verified", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "is_superuser", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    ]


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
    """Create the users table and its active-flag index."""
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=ID_LENGTH), nullable=False),
        *_account_columns(),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(ACTIVE_INDEX, "users", ["is_active"])


def downgrade() -> None:
    """Drop the users table after copying its rows into a backup table."""
    preserve_and_drop_table("users", indexes=(ACTIVE_INDEX,))
