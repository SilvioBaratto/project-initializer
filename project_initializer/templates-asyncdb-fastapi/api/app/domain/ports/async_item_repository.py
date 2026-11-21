"""Async twins of the item repository and unit of work ports.

They carry the same contracts as ``ItemRepositoryPort`` and ``UnitOfWorkPort``
and differ only in that every method is awaited, so a use case written against
them runs on an ``AsyncSession`` without touching the sync path.

Errors follow the sync ports: a write that violates a constraint raises
``ConflictError`` from the repository call itself, with the transaction already
rolled back, and a store that cannot be reached raises ``ExternalServiceError``
from any method once the error leaves the adapter's session scope. Adapters
never let a driver exception escape that scope.
"""

from typing import Protocol, runtime_checkable

from app.domain.entities.item import Item, ItemChanges, NewItem


@runtime_checkable
class AsyncItemRepositoryPort(Protocol):
    """Reads and writes ``Item`` entities without blocking the event loop."""

    async def get(self, item_id: str) -> Item | None:
        """Fetch one item.

        Args:
            item_id: Identifier of the item.

        Returns:
            The item, or None when no item has that id.
        """
        ...

    async def list_page(self, *, offset: int, limit: int) -> list[Item]:
        """Fetch one page of items, newest ``created_at`` first and then by id.

        Args:
            offset: Number of items to skip. Must not be negative.
            limit: Maximum number of items to return. Must be positive.

        Returns:
            Up to ``limit`` items; empty when ``offset`` is past the last item.
        """
        ...

    async def count(self) -> int:
        """Return the total number of items, regardless of paging."""
        ...

    async def add(self, new_item: NewItem) -> Item:
        """Stage a new item.

        Args:
            new_item: Validated values of the item to create.

        Returns:
            The item as stored, with its generated id and timestamps.

        Raises:
            ConflictError: A constraint rejected the insert.
        """
        ...

    async def update(self, item_id: str, changes: ItemChanges) -> Item | None:
        """Apply a partial update.

        Args:
            item_id: Identifier of the item to change.
            changes: Fields to change; unset fields stay as they are.

        Returns:
            The updated item, or None when no item has that id, including when
            another transaction deleted it after it was read.

        Raises:
            ConflictError: A constraint rejected the update.
        """
        ...

    async def delete(self, item_id: str) -> bool:
        """Remove an item.

        Args:
            item_id: Identifier of the item to remove.

        Returns:
            True when an item was removed, False when no item has that id.

        Raises:
            ConflictError: A constraint rejected the delete.
        """
        ...


@runtime_checkable
class AsyncUnitOfWorkPort(Protocol):
    """Makes the writes staged by async repositories permanent, or discards them."""

    async def commit(self) -> None:
        """Make all staged writes permanent.

        Raises:
            ConflictError: A uniqueness or integrity constraint rejected the
                writes. The adapter has already rolled back when this is raised.
            ExternalServiceError: The store is unavailable. Raised once the
                error leaves the adapter's session scope.
        """
        ...

    async def rollback(self) -> None:
        """Discard all staged writes."""
        ...
