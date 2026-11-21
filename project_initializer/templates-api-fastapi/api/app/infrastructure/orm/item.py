"""ORM record for the ``items`` table."""

import sqlalchemy as sa
from sqlalchemy import Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import ITEM_DESCRIPTION_MAX_LENGTH, ITEM_NAME_MAX_LENGTH
from app.infrastructure.orm.base import Base, StringIdPrimaryKeyMixin, TimestampMixin


class ItemRecord(StringIdPrimaryKeyMixin, TimestampMixin, Base):
    """Persistence shape of an item.

    It never leaves the infrastructure layer: repositories map it to the
    ``Item`` entity before returning anything.
    """

    __tablename__ = "items"
    # Pages are listed newest first, so the sort runs on the index.
    __table_args__ = (Index("idx_items_created_at", "created_at"),)

    name: Mapped[str] = mapped_column(String(ITEM_NAME_MAX_LENGTH))
    description: Mapped[str | None] = mapped_column(String(ITEM_DESCRIPTION_MAX_LENGTH))
    price: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(server_default=sa.true())

    def __repr__(self) -> str:
        return f"<ItemRecord id={self.id}>"
