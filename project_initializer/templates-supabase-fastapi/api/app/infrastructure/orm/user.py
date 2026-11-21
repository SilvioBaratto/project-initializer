"""ORM record for the ``profiles`` table of the Supabase variant.

The module is named ``user`` because the layer merge replaces the base ``user``
module by path, and ``app.infrastructure.orm`` imports it under that name to
register the table. Keeping the name leaves the package untouched.
"""

from typing import Any

from sqlalchemy import JSON, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import ENTITY_ID_LENGTH
from app.infrastructure.orm.base import Base, TimestampMixin

DISPLAY_NAME_MAX_LENGTH = 100
AVATAR_URL_MAX_LENGTH = 500


class ProfileRecord(TimestampMixin, Base):
    """Profile data attached to a Supabase user.

    Supabase Auth owns credentials and identity in its own ``auth.users`` table.
    This table only extends it with application data, so it stores no password
    or authentication field. It never leaves the infrastructure layer.

    The primary key is the Supabase user id (a UUID in text form). It is
    supplied by the caller and never generated here. The model declares no
    foreign key to ``auth.users``, which belongs to Supabase and is not part of
    this schema, so the caller is what keeps a profile paired with its user.
    """

    __tablename__ = "profiles"
    __table_args__ = (Index("idx_profiles_display_name", "display_name"),)

    id: Mapped[str] = mapped_column(String(ENTITY_ID_LENGTH), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(DISPLAY_NAME_MAX_LENGTH))
    avatar_url: Mapped[str | None] = mapped_column(String(AVATAR_URL_MAX_LENGTH))
    bio: Mapped[str | None] = mapped_column(Text)
    # Binary JSON gives PostgreSQL an indexable document type; the generic JSON
    # variant keeps the table creatable on the SQLite database the tests use.
    preferences: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )

    def __repr__(self) -> str:
        return f"<ProfileRecord id={self.id}>"
