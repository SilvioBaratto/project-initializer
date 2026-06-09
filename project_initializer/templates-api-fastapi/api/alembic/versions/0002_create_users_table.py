"""create users table

Revision ID: 0002_create_users
Revises: 0001_create_items
Create Date: 2026-06-09

Hand-written (scaffold ships without a live DB connection). Additive: creates
the ``users`` table only — never touches existing data. Chained after the items
migration; Alembic's alembic_version table guarantees it runs at most once.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_create_users"
down_revision: Union[str, Sequence[str], None] = "0001_create_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("idx_users_username", "users", ["username"])
    op.create_index("idx_users_is_active", "users", ["is_active"])


def downgrade() -> None:
    op.drop_index("idx_users_is_active", table_name="users")
    op.drop_index("idx_users_username", table_name="users")
    op.drop_table("users")
