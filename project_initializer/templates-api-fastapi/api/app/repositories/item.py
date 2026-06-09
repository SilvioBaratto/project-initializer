"""Item repository for data access over the sync Session."""

from sqlalchemy.orm import Session

from app.models.item import Item
from app.repositories.base import BaseRepository
from app.schemas.item import ItemCreate, ItemUpdate


class ItemRepository(BaseRepository[Item, ItemCreate, ItemUpdate]):
    """Repository for Item-specific database operations."""

    def __init__(self, session: Session):
        super().__init__(Item, session)
