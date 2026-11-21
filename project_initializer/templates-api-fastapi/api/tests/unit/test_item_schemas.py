"""Unit tests for the item request and response schemas."""

import math

import pytest
from pydantic import ValidationError

from app.api.schemas.item import ItemCreate, ItemListResponse, ItemResponse, ItemUpdate
from app.application.commands.item import CreateItemCommand, UpdateItemCommand
from app.application.dto.item import ItemDTO
from app.domain.constants import (
    ITEM_DESCRIPTION_MAX_LENGTH,
    ITEM_NAME_MAX_LENGTH,
    ITEM_PRICE_MAX,
)
from app.domain.entities.item import UNSET
from tests.fakes import FIXED_NOW, make_item
from tests.schema_helpers import error_fields

pytestmark = pytest.mark.unit

ITEM_ID = "item-1"
NEW_PRICE = 1.5
TOO_LONG_NAME = "n" * (ITEM_NAME_MAX_LENGTH + 1)
TOO_LONG_DESCRIPTION = "d" * (ITEM_DESCRIPTION_MAX_LENGTH + 1)

ACCEPTED_FIELD_VALUES = [
    pytest.param("name", "n", id="name-lower-bound"),
    pytest.param("name", "n" * ITEM_NAME_MAX_LENGTH, id="name-upper-bound"),
    pytest.param("description", "", id="description-empty"),
    pytest.param(
        "description", "d" * ITEM_DESCRIPTION_MAX_LENGTH, id="description-upper-bound"
    ),
    pytest.param("description", None, id="description-absent"),
    pytest.param("price", 0, id="price-free"),
    pytest.param("price", ITEM_PRICE_MAX, id="price-upper-bound"),
    pytest.param("price", None, id="price-absent"),
]
REJECTED_FIELD_VALUES = [
    pytest.param("name", "", id="name-empty"),
    pytest.param("name", TOO_LONG_NAME, id="name-over-limit"),
    pytest.param("description", TOO_LONG_DESCRIPTION, id="description-over-limit"),
    pytest.param("price", -0.01, id="price-negative"),
    pytest.param("price", ITEM_PRICE_MAX * 2, id="price-over-limit"),
    pytest.param("price", math.nan, id="price-nan"),
    pytest.param("price", math.inf, id="price-infinity"),
    pytest.param("price", -math.inf, id="price-negative-infinity"),
    pytest.param("price", "free", id="price-not-a-number"),
    pytest.param("is_active", "maybe", id="flag-not-a-boolean"),
]


@pytest.mark.parametrize(("field", "value"), ACCEPTED_FIELD_VALUES)
def test_when_item_create_field_is_within_bounds_then_it_is_accepted(field, value):
    """when a field sits on an allowed boundary, ItemCreate accepts the payload.

    Validates app.api.schemas.item.ItemCreate.
    """
    payload = {"name": "Widget", field: value}

    item = ItemCreate(**payload)

    assert getattr(item, field) == value


@pytest.mark.parametrize(("field", "value"), REJECTED_FIELD_VALUES)
def test_when_item_create_field_breaks_a_bound_then_only_that_field_is_rejected(
    field, value
):
    """when a field is outside its bound, ItemCreate rejects it and names the field.

    Validates app.api.schemas.item.ItemCreate.
    """
    payload = {"name": "Widget", field: value}

    with pytest.raises(ValidationError) as error:
        ItemCreate(**payload)

    assert error_fields(error) == {field}


def test_when_item_create_has_no_name_then_it_is_rejected():
    """when the name is missing, ItemCreate rejects the payload.

    Validates app.api.schemas.item.ItemCreate.
    """
    with pytest.raises(ValidationError) as error:
        ItemCreate()

    assert error_fields(error) == {"name"}


def test_when_item_create_has_only_a_name_then_optional_fields_take_their_defaults():
    """when only the name is given, the optional fields are empty and it is active.

    Validates app.api.schemas.item.ItemCreate.
    """
    item = ItemCreate(name="Minimal")

    assert item.description is None
    assert item.price is None
    assert item.is_active is True


def test_when_item_create_is_converted_then_the_command_carries_every_field():
    """when ItemCreate is converted, the command holds the same values.

    Validates app.api.schemas.item.ItemCreate.to_command().
    """
    item = ItemCreate(
        name="Widget", description="A widget", price=9.99, is_active=False
    )

    assert item.to_command() == CreateItemCommand(
        name="Widget", description="A widget", price=9.99, is_active=False
    )


@pytest.mark.parametrize(("field", "value"), ACCEPTED_FIELD_VALUES)
def test_when_item_update_field_is_within_bounds_then_it_is_accepted(field, value):
    """when a field sits on an allowed boundary, ItemUpdate accepts it.

    Validates app.api.schemas.item.ItemUpdate.
    """
    update = ItemUpdate(**{field: value})

    assert getattr(update, field) == value


@pytest.mark.parametrize(("field", "value"), REJECTED_FIELD_VALUES)
def test_when_item_update_field_breaks_a_bound_then_only_that_field_is_rejected(
    field, value
):
    """when a field is outside its bound, ItemUpdate rejects it and names the field.

    Validates app.api.schemas.item.ItemUpdate.
    """
    with pytest.raises(ValidationError) as error:
        ItemUpdate(**{field: value})

    assert error_fields(error) == {field}


def test_when_item_update_is_empty_then_the_command_changes_nothing():
    """when no field is sent, every command field stays unset.

    Validates app.api.schemas.item.ItemUpdate.to_command().
    """
    command = ItemUpdate().to_command(ITEM_ID)

    assert command == UpdateItemCommand(item_id=ITEM_ID)
    assert command.name is UNSET
    assert command.is_active is UNSET


def test_when_item_update_sends_some_fields_then_only_those_are_set():
    """when two fields are sent, the command sets them and leaves the rest unset.

    Validates app.api.schemas.item.ItemUpdate.to_command().
    """
    command = ItemUpdate(name="Renamed", price=NEW_PRICE).to_command(ITEM_ID)

    assert command.name == "Renamed"
    assert command.price == NEW_PRICE
    assert command.description is UNSET
    assert command.is_active is UNSET


def test_when_item_update_sends_explicit_nulls_then_the_command_clears_them():
    """when description and price are sent as null, the command clears them.

    An explicit null is different from an omitted field, which stays unset.

    Validates app.api.schemas.item.ItemUpdate.to_command().
    """
    command = ItemUpdate.model_validate(
        {"description": None, "price": None}
    ).to_command(ITEM_ID)

    assert command.description is None
    assert command.price is None
    assert command.name is UNSET


def test_when_item_response_is_built_from_a_dto_then_every_field_is_mapped():
    """when an ItemDTO is validated, ItemResponse exposes the same seven fields.

    Validates app.api.schemas.item.ItemResponse.
    """
    dto = ItemDTO.from_entity(make_item(ITEM_ID, price=9.99))

    response = ItemResponse.model_validate(dto)

    assert response.model_dump(mode="json") == {
        "id": ITEM_ID,
        "name": "Widget",
        "description": None,
        "price": 9.99,
        "is_active": True,
        "created_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
        "updated_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
    }


def test_when_item_list_response_is_built_then_it_carries_items_and_total():
    """when a page is serialised, the list response holds the items and the total.

    Validates app.api.schemas.item.ItemListResponse.
    """
    page = ItemListResponse(items=[], total=42)

    assert page.model_dump() == {"items": [], "total": 42}
