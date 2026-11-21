"""SQLAlchemy implementation of the item repository port."""

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.domain.entities.item import Item, ItemChanges, NewItem
from app.infrastructure.orm.item import ItemRecord
from app.infrastructure.repositories.item_mapping import (
    apply_changes,
    count_statement,
    page_statement,
    to_entity,
    to_record,
)
from app.infrastructure.unit_of_work import flush_or_conflict


class SqlAlchemyItemRepository:
    """Stores items through a session and returns domain entities.

    Writes are flushed, never committed: the unit of work owns the transaction.
    Every flush goes through ``flush_or_conflict``, so an integrity violation is
    a ``ConflictError`` at the moment the write is staged.
    """

    def __init__(self, session: Session) -> None:
        """Bind the repository to a session.

        Args:
            session: Session shared with the unit of work of the same request.
        """
        self._session = session

    def get(self, item_id: str) -> Item | None:
        """Fetch one item, or None when the id is unknown."""
        record = self._session.get(ItemRecord, item_id)
        return to_entity(record) if record else None

    def list_page(self, *, offset: int, limit: int) -> list[Item]:
        """Fetch one page of items, newest first and then by id."""
        statement = page_statement(offset=offset, limit=limit)
        return [to_entity(record) for record in self._session.scalars(statement)]

    def count(self) -> int:
        """Return the total number of items."""
        return self._session.scalar(count_statement()) or 0

    def add(self, new_item: NewItem) -> Item:
        """Stage a new item and return it with its generated id and timestamps.

        Raises:
            ConflictError: A constraint rejected the insert; the session has
                been rolled back.
        """
        record = to_record(new_item)
        self._session.add(record)
        flush_or_conflict(self._session)
        self._session.refresh(record)
        return to_entity(record)

    def update(self, item_id: str, changes: ItemChanges) -> Item | None:
        """Apply a partial update, or return None when the id is unknown.

        Returns None as well when another transaction deleted the item between
        the read and the write, after rolling the session back.

        Raises:
            ConflictError: A constraint rejected the update; the session has
                been rolled back.
        """
        record = self._session.get(ItemRecord, item_id)
        if record is None:
            return None
        apply_changes(record, changes)
        try:
            flush_or_conflict(self._session)
        except StaleDataError:
            self._session.rollback()
            return None
        # updated_at is set by the database, so the loaded value is stale.
        self._session.refresh(record)
        return to_entity(record)

    def delete(self, item_id: str) -> bool:
        """Remove an item; return False when the id is unknown.

        Raises:
            ConflictError: A constraint rejected the delete; the session has
                been rolled back.
        """
        record = self._session.get(ItemRecord, item_id)
        if record is None:
            return False
        self._session.delete(record)
        flush_or_conflict(self._session)
        return True
