"""Declarative base and the column mixins every record reuses."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.constants import ENTITY_ID_LENGTH


class Base(DeclarativeBase):
    """Base class of every ORM record."""

    # A bare DateTime maps to "timestamp without time zone" on PostgreSQL, which
    # drops the UTC offset, so every datetime column is timezone-aware.
    type_annotation_map = {datetime: DateTime(timezone=True)}


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at``, both set by the database.

    ``updated_at`` is refreshed by SQLAlchemy on every ORM update. A raw SQL
    update bypasses that, so write through the ORM.
    """

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class StringIdPrimaryKeyMixin:
    """Adds a textual UUID primary key.

    A string rather than a native UUID type keeps the schema identical on
    PostgreSQL and on the SQLite database the tests use.
    """

    id: Mapped[str] = mapped_column(
        String(ENTITY_ID_LENGTH), primary_key=True, default=lambda: str(uuid.uuid4())
    )
