"""Item repository port: the data access the item use cases depend on.

Application code is typed against this protocol, never against a concrete
repository, so the business rules import nothing from infrastructure. Methods
only flush; the unit of work (``UnitOfWorkPort``) decides when to commit.

Errors: a write that violates a constraint raises ``ConflictError`` from the
repository call itself, because flushing is where the database checks it, and
the adapter has already rolled the transaction back. A store that cannot be
reached raises ``ExternalServiceError`` from any method, once the error leaves
the adapter's session scope. Adapters never let a driver exception escape that
scope, so no SQL text reaches a use case or a log.
"""

from typing import Protocol, runtime_checkable

from app.domain.entities.item import Item, ItemChanges, NewItem


@runtime_checkable
class ItemRepositoryPort(Protocol):
    """Reads and writes ``Item`` entities."""

    def get(self, item_id: str) -> Item | None:
        """Fetch one item.

        Args:
            item_id: Identifier of the item.

        Returns:
            The item, or None when no item has that id.
        """
        ...

    def list_page(self, *, offset: int, limit: int) -> list[Item]:
        """Fetch one page of items, newest ``created_at`` first and then by id.

        Args:
            offset: Number of items to skip. Must not be negative.
            limit: Maximum number of items to return. Must be positive.

        Returns:
            Up to ``limit`` items; empty when ``offset`` is past the last item.
        """
        ...

    def count(self) -> int:
        """Return the total number of items, regardless of paging."""
        ...

    def add(self, new_item: NewItem) -> Item:
        """Stage a new item.

        Args:
            new_item: Validated values of the item to create.

        Returns:
            The item as stored, with its generated id and timestamps.

        Raises:
            ConflictError: A constraint rejected the insert.
        """
        ...

    def update(self, item_id: str, changes: ItemChanges) -> Item | None:
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

    def delete(self, item_id: str) -> bool:
        """Remove an item.

        Args:
            item_id: Identifier of the item to remove.

        Returns:
            True when an item was removed, False when no item has that id.

        Raises:
            ConflictError: A constraint rejected the delete.
        """
        ...
