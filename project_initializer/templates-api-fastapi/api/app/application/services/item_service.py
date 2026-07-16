"""Item service holding the business logic for item CRUD.

Depends only on the domain ``ItemRepositoryPort`` — no SQLAlchemy, no FastAPI,
no infrastructure import — so the business rules can be tested against a fake
repository and the boundary stays clean (enforced by ``tests/unit/test_architecture.py``).

The service owns the transaction boundary (``commit``); the repository only
flushes. Reads (``list``/``get``) do not commit. Missing-id ``get``/``update``/
``delete`` return ``None``/``False`` so the router maps them to HTTP 404 —
HTTP concerns stay out of this layer.
"""

from typing import Any, Optional, Sequence

from app.domain.ports.item_repository import ItemRepositoryPort


class ItemService:
    """Business logic for items, delegating data access to an ItemRepositoryPort."""

    def __init__(self, repository: ItemRepositoryPort):
        self.repository = repository

    def list(self, skip: int = 0, limit: int = 100) -> Sequence[Any]:
        """Return a paginated list of items."""
        return self.repository.get_multi(skip=skip, limit=limit)

    def count(self) -> int:
        """Return the total number of items (full row count, not page size)."""
        return self.repository.count()

    def get(self, item_id: str) -> Optional[Any]:
        """Return a single item by id, or None if it does not exist."""
        return self.repository.get(item_id)

    def create(self, item_in: Any) -> Any:
        """Create an item and commit the transaction."""
        item = self.repository.create(item_in)
        self.repository.commit()
        return item

    def update(self, item_id: str, item_in: Any) -> Optional[Any]:
        """Update an item and commit, or return None if it does not exist."""
        item = self.repository.update(item_id, item_in)
        if item is None:
            return None
        self.repository.commit()
        return item

    def delete(self, item_id: str) -> bool:
        """Delete an item and commit, or return False if it does not exist."""
        deleted = self.repository.delete(item_id)
        if deleted:
            self.repository.commit()
        return deleted
