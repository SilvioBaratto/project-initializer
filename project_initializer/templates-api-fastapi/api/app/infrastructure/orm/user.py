"""ORM record for the ``users`` table, used by the token authentication variant."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import (
    EMAIL_MAX_LENGTH,
    PERSON_NAME_MAX_LENGTH,
    USERNAME_MAX_LENGTH,
)
from app.infrastructure.orm.base import Base, StringIdPrimaryKeyMixin, TimestampMixin

# Sized for a bcrypt hash (60 characters) with room for a stronger algorithm.
PASSWORD_HASH_MAX_LENGTH = 255


class UserRecord(StringIdPrimaryKeyMixin, TimestampMixin, Base):
    """Persistence shape of a user account.

    It never leaves the infrastructure layer. The unique constraints on
    ``email`` and ``username`` already create the indexes lookups need.
    """

    __tablename__ = "users"
    __table_args__ = (Index("idx_users_is_active", "is_active"),)

    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), unique=True)
    username: Mapped[str | None] = mapped_column(
        String(USERNAME_MAX_LENGTH), unique=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(PASSWORD_HASH_MAX_LENGTH))
    first_name: Mapped[str | None] = mapped_column(String(PERSON_NAME_MAX_LENGTH))
    last_name: Mapped[str | None] = mapped_column(String(PERSON_NAME_MAX_LENGTH))
    is_active: Mapped[bool] = mapped_column(server_default=sa.true())
    is_verified: Mapped[bool] = mapped_column(server_default=sa.false())
    is_superuser: Mapped[bool] = mapped_column(server_default=sa.false())
    last_login: Mapped[datetime | None] = mapped_column()

    def __repr__(self) -> str:
        return f"<UserRecord id={self.id}>"
