"""Item service holding the business logic for item CRUD.

The service owns the transaction boundary (``commit``); the repository only
flushes. Reads (``list``/``get``) do not commit. Missing-id ``get``/``update``/
``delete`` return ``None``/``False`` so the router maps them to HTTP 404 —
HTTP concerns stay out of this layer.
"""

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.item import Item
from app.repositories.item import ItemRepository
from app.schemas.item import ItemCreate, ItemUpdate


class ItemService:
    """Business logic for items, delegating data access to ItemRepository."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = ItemRepository(session)

    def list(self, skip: int = 0, limit: int = 100) -> Sequence[Item]:
        """Return a paginated list of items."""
        return self.repository.get_multi(skip=skip, limit=limit)

    def count(self) -> int:
        """Return the total number of items (full row count, not page size)."""
        return self.repository.count()

    def get(self, item_id: str) -> Optional[Item]:
        """Return a single item by id, or None if it does not exist."""
        return self.repository.get(item_id)

    def create(self, item_in: ItemCreate) -> Item:
        """Create an item and commit the transaction."""
        item = self.repository.create(item_in)
        self.session.commit()
        return item

    def update(self, item_id: str, item_in: ItemUpdate) -> Optional[Item]:
        """Update an item and commit, or return None if it does not exist."""
        item = self.repository.update(item_id, item_in)
        if item is None:
            return None
        self.session.commit()
        return item

    def delete(self, item_id: str) -> bool:
        """Delete an item and commit, or return False if it does not exist."""
        deleted = self.repository.delete(item_id)
        if deleted:
            self.session.commit()
        return deleted
