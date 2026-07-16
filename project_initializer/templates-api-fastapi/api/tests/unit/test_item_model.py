"""Unit tests for the Item model, schema module, and table registration.

Scope: issue #7 (persistence foundation). Covers the SQLAlchemy ``Item`` model,
its registration on ``Base.metadata`` (so ``create_all`` builds the ``items``
table on the SQLite test engine), and the ``app.api.schemas.item`` module re-exports.
Full ``ItemCreate`` validation matrices live in the dedicated schema test suite.
"""

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect


@pytest.mark.unit
def test_when_metadata_create_all_runs_then_items_table_exists(test_engine):
    """when metadata is created, the items table is returned by the inspector."""
    table_names = inspect(test_engine).get_table_names()
    assert "items" in table_names


@pytest.mark.unit
def test_when_item_model_imported_then_columns_match_schema(test_engine):
    """when the Item model is imported, the items table exposes the expected columns."""
    columns = {col["name"] for col in inspect(test_engine).get_columns("items")}
    assert columns == {
        "id",
        "name",
        "description",
        "price",
        "is_active",
        "created_at",
        "updated_at",
    }


@pytest.mark.unit
def test_when_item_persisted_then_fields_round_trip(db_session):
    """when an Item is saved, its generated id and timestamps round-trip from the DB."""
    from app.infrastructure.orm import Item

    item = Item(name="Widget", description="A widget", price=9.99, is_active=True)
    db_session.add(item)
    db_session.flush()
    db_session.refresh(item)

    assert isinstance(item.id, str) and len(item.id) == 36
    assert item.name == "Widget"
    assert item.created_at is not None
    assert item.updated_at is not None


@pytest.mark.unit
def test_when_item_schemas_imported_from_package_then_they_resolve():
    """when Item schemas are imported from app.api.schemas, the package re-exports resolve."""
    from app.api.schemas import (  # noqa: F401
        ItemBase,
        ItemCreate,
        ItemUpdate,
        ItemResponse,
        ItemListResponse,
    )

    assert ItemResponse.model_config.get("from_attributes") is True


@pytest.mark.unit
def test_when_itemcreate_given_invalid_input_then_validation_error():
    """when ItemCreate gets an empty name or negative price, ValidationError is raised."""
    from app.api.schemas import ItemCreate

    with pytest.raises(ValidationError):
        ItemCreate(name="", price=1.0)
    with pytest.raises(ValidationError):
        ItemCreate(name="ok", price=-1.0)
