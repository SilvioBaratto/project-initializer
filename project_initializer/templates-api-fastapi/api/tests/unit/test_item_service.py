"""Unit tests for ItemService over the sync Session.

Scope: issue #8. Exercises create/get/list/update/delete business logic against
the in-memory SQLite ``db_session`` fixture. The service owns commits; the
repository only flushes. Missing-id reads/updates/deletes return ``None``/``False``
so the router layer can map them to HTTP 404.
"""

import pytest

from app.schemas import ItemCreate, ItemUpdate
from app.services.item_service import ItemService


def _make(session, **overrides):
    """Create an item through the service and return it."""
    payload = {"name": "Widget", "description": "A widget", "price": 9.99}
    payload.update(overrides)
    return ItemService(session).create(ItemCreate(**payload))


@pytest.mark.unit
def test_when_item_created_then_persisted_item_is_returned(db_session):
    """when an item is created, the persisted item with an id is returned."""
    item = _make(db_session)

    assert item.id is not None
    assert item.name == "Widget"
    assert item.price == 9.99


@pytest.mark.unit
def test_when_existing_id_fetched_then_item_is_returned(db_session):
    """when an existing id is fetched, the matching item is returned."""
    created = _make(db_session)

    fetched = ItemService(db_session).get(created.id)

    assert fetched is not None
    assert fetched.id == created.id


@pytest.mark.unit
def test_when_missing_id_fetched_then_none_is_returned(db_session):
    """when a missing id is fetched, None is returned."""
    assert ItemService(db_session).get("does-not-exist") is None


@pytest.mark.unit
def test_when_items_listed_then_all_created_items_are_returned(db_session):
    """when items are listed, every created item is returned."""
    _make(db_session, name="A")
    _make(db_session, name="B")

    items = ItemService(db_session).list()

    assert len(items) >= 2


@pytest.mark.unit
def test_when_existing_item_updated_then_updated_item_is_returned(db_session):
    """when an existing item is updated, the updated item is returned."""
    created = _make(db_session)

    updated = ItemService(db_session).update(
        created.id, ItemUpdate(name="Renamed", price=1.0)
    )

    assert updated is not None
    assert updated.name == "Renamed"
    assert updated.price == 1.0


@pytest.mark.unit
def test_when_missing_item_updated_then_none_is_returned(db_session):
    """when a missing item is updated, None is returned."""
    result = ItemService(db_session).update("nope", ItemUpdate(name="x"))

    assert result is None


@pytest.mark.unit
def test_when_existing_item_deleted_then_true_is_returned(db_session):
    """when an existing item is deleted, True is returned and it is gone."""
    created = _make(db_session)
    service = ItemService(db_session)

    assert service.delete(created.id) is True
    assert service.get(created.id) is None


@pytest.mark.unit
def test_when_missing_item_deleted_then_false_is_returned(db_session):
    """when a missing item is deleted, False is returned."""
    assert ItemService(db_session).delete("nope") is False
