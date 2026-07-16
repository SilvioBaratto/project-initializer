"""Item repository for data access over the sync Session."""

from sqlalchemy.orm import Session

from app.infrastructure.orm.item import Item
from app.infrastructure.repositories.base import BaseRepository
from app.api.schemas.item import ItemCreate, ItemUpdate


class ItemRepository(BaseRepository[Item, ItemCreate, ItemUpdate]):
    """Repository for Item-specific database operations."""

    def __init__(self, session: Session):
        super().__init__(Item, session)
