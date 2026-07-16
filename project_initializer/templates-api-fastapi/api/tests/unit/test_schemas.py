"""Unit tests for Pydantic schema validation (issue #11).

Asserts the shared ``ItemCreate`` contract: ``name`` length bounds (1-100) and
non-negative ``price``. Pure validation — no DB, no client, plain ``assert``.
"""

import pytest
from pydantic import ValidationError

from app.api.schemas import ItemCreate


@pytest.mark.unit
def test_when_name_is_empty_then_validation_error_is_raised():
    """when name is empty, a ValidationError is raised."""
    with pytest.raises(ValidationError):
        ItemCreate(name="")


@pytest.mark.unit
def test_when_name_exceeds_100_chars_then_validation_error_is_raised():
    """when name exceeds 100 chars, a ValidationError is raised."""
    with pytest.raises(ValidationError):
        ItemCreate(name="x" * 101)


@pytest.mark.unit
def test_when_price_is_negative_then_validation_error_is_raised():
    """when price is negative, a ValidationError is raised."""
    with pytest.raises(ValidationError):
        ItemCreate(name="Widget", price=-1.0)


@pytest.mark.unit
def test_when_payload_is_valid_then_item_create_is_accepted():
    """when the payload is valid, ItemCreate accepts it and exposes the fields."""
    item = ItemCreate(name="Widget", description="A widget", price=9.99)

    assert item.name == "Widget"
    assert item.price == 9.99
    assert item.is_active is True


@pytest.mark.unit
def test_when_only_name_given_then_optional_fields_default():
    """when only name is given, optional fields take their defaults."""
    item = ItemCreate(name="Minimal")

    assert item.description is None
    assert item.price is None
    assert item.is_active is True
