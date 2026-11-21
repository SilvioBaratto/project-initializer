"""In-memory fakes of the domain ports, for tests that must not touch I/O."""

from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, datetime

from app.domain.entities.authenticated_user import AuthenticatedUser
from app.domain.entities.item import Item, ItemChanges, NewItem

FIXED_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)

FAKE_CLOCK_START_SECONDS = 1_000.0

TEST_USER = AuthenticatedUser(
    id="test-user",
    auth_method="test",
    email="test-user@example.com",
    username="test-user",
    roles=("tester",),
)


def make_item(
    item_id: str = "item-1",
    *,
    name: str = "Widget",
    description: str | None = None,
    price: float | None = None,
    is_active: bool = True,
    created_at: datetime = FIXED_NOW,
) -> Item:
    """Build a stored ``Item`` whose ``updated_at`` equals its ``created_at``.

    Args:
        item_id: Identifier of the item.
        name: Display name.
        description: Optional description.
        price: Optional price.
        is_active: Whether the item is active.
        created_at: Creation instant; ``updated_at`` is set to the same value.

    Returns:
        A frozen ``Item`` that was never modified since creation.
    """
    return Item(
        id=item_id,
        name=name,
        description=description,
        price=price,
        is_active=is_active,
        created_at=created_at,
        updated_at=created_at,
    )


class FakeClock:
    """Monotonic clock, callable like ``time.monotonic``, advanced by hand."""

    def __init__(self) -> None:
        self.now = FAKE_CLOCK_START_SECONDS

    def __call__(self) -> float:
        """Return the current fake time in seconds."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward by ``seconds``."""
        self.now += seconds


class FakeItemRepository:
    """Dict-backed ``ItemRepositoryPort`` that mirrors the real listing order."""

    def __init__(self, items: Iterable[Item] = ()) -> None:
        """Seed the store.

        Args:
            items: Items that already exist.
        """
        self._items: dict[str, Item] = {item.id: item for item in items}
        self._created_count = 0

    def get(self, item_id: str) -> Item | None:
        """Return the stored item, or None when the id is unknown."""
        return self._items.get(item_id)

    def list_page(self, *, offset: int, limit: int) -> list[Item]:
        """Return a slice ordered newest ``created_at`` first, then by id."""
        newest_first = sorted(
            self._items.values(),
            key=lambda item: (-item.created_at.timestamp(), item.id),
        )
        return newest_first[offset : offset + limit]

    def count(self) -> int:
        """Return how many items are stored."""
        return len(self._items)

    def add(self, new_item: NewItem) -> Item:
        """Store the item under a sequential id (``item-1``, ``item-2``, ...)."""
        self._created_count += 1
        created = Item(
            id=f"item-{self._created_count}",
            name=new_item.name,
            description=new_item.description,
            price=new_item.price,
            is_active=new_item.is_active,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )
        self._items[created.id] = created
        return created

    def update(self, item_id: str, changes: ItemChanges) -> Item | None:
        """Apply the provided fields, or return None when the id is unknown."""
        existing = self._items.get(item_id)
        if existing is None:
            return None
        updated = replace(existing, **changes.provided_fields())
        self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> bool:
        """Remove the item and report whether it existed."""
        return self._items.pop(item_id, None) is not None


class FakeUnitOfWork:
    """``UnitOfWorkPort`` that counts commits; no fake store stages writes."""

    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        """Count one commit."""
        self.commits += 1

    def rollback(self) -> None:
        """Do nothing: the port requires it, but no fake store stages writes."""
