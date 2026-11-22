"""Translation between the ``Item`` entities and the ``ItemRecord`` ORM rows.

Shared by the sync and the async repositories so both read and write items the
same way and neither lets an ORM object cross into the application layer.
"""

from sqlalchemy import Select, func, select

from app.domain.entities.item import Item, ItemChanges, NewItem
from app.infrastructure.orm.item import ItemRecord


def to_entity(record: ItemRecord) -> Item:
    """Copy a row into the immutable domain entity.

    Args:
        record: A persisted row whose server-generated columns are loaded.

    Returns:
        An ``Item`` that holds no reference to the session.
    """
    return Item(
        id=record.id,
        name=record.name,
        description=record.description,
        price=record.price,
        is_active=record.is_active,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def to_record(new_item: NewItem) -> ItemRecord:
    """Build a row for an item that does not exist yet.

    Args:
        new_item: Validated values of the item.

    Returns:
        A transient row; its id and timestamps are assigned on flush.
    """
    return ItemRecord(
        name=new_item.name,
        description=new_item.description,
        price=new_item.price,
        is_active=new_item.is_active,
    )


def apply_changes(record: ItemRecord, changes: ItemChanges) -> None:
    """Copy the fields a caller set onto a row.

    Only the names ``ItemChanges.provided_fields`` returns are written, and all
    of them are columns, so a caller cannot reach ``id`` or the timestamps.

    Args:
        record: The row to change.
        changes: A partial update; unset fields are left alone and a field set
            to ``None`` clears the column.
    """
    for field_name, value in changes.provided_fields().items():
        setattr(record, field_name, value)


def page_statement(*, offset: int, limit: int) -> Select[ItemRecord]:
    """Select one page of rows, newest first.

    Args:
        offset: Number of rows to skip.
        limit: Maximum number of rows.

    Returns:
        A statement ordered by ``created_at`` descending and then by ``id``, so
        rows created in the same instant keep a stable order across pages.
    """
    return (
        select(ItemRecord)
        .order_by(ItemRecord.created_at.desc(), ItemRecord.id)
        .offset(offset)
        .limit(limit)
    )


def count_statement() -> Select[int]:
    """Select the total number of item rows."""
    return select(func.count()).select_from(ItemRecord)
