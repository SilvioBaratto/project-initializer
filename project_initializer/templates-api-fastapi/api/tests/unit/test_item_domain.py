"""Unit tests for the item and user domain entities and their business rules."""

import math
from dataclasses import FrozenInstanceError

import pytest

from app.domain.constants import (
    ITEM_DESCRIPTION_MAX_LENGTH,
    ITEM_NAME_MAX_LENGTH,
    ITEM_PRICE_MAX,
)
from app.domain.entities.authenticated_user import AuthenticatedUser
from app.domain.entities.item import UNSET, ItemChanges, NewItem
from app.domain.exceptions import DomainValidationError
from app.domain.ports.item_repository import ItemRepositoryPort
from app.domain.ports.unit_of_work import UnitOfWorkPort
from tests.fakes import TEST_USER, FakeItemRepository, FakeUnitOfWork, make_item

PRICE_ABOVE_MAX = math.nextafter(ITEM_PRICE_MAX, math.inf)

INVALID_NAMES = [
    pytest.param("", id="empty"),
    pytest.param("   ", id="blank"),
    pytest.param("\t\n", id="whitespace-control-characters"),
    pytest.param("a" * (ITEM_NAME_MAX_LENGTH + 1), id="one-over-max"),
]
VALID_NAMES = [
    pytest.param("a", id="one-character"),
    pytest.param("a" * ITEM_NAME_MAX_LENGTH, id="at-max"),
]
INVALID_DESCRIPTIONS = [
    pytest.param("a" * (ITEM_DESCRIPTION_MAX_LENGTH + 1), id="one-over-max"),
]
VALID_DESCRIPTIONS = [
    pytest.param("", id="empty"),
    pytest.param("a" * ITEM_DESCRIPTION_MAX_LENGTH, id="at-max"),
]
INVALID_PRICES = [
    pytest.param(-0.01, id="negative"),
    pytest.param(-math.inf, id="negative-infinity"),
    pytest.param(math.inf, id="infinity"),
    pytest.param(math.nan, id="not-a-number"),
    pytest.param(PRICE_ABOVE_MAX, id="above-max"),
]
VALID_PRICES = [
    pytest.param(0, id="zero"),
    pytest.param(0.01, id="small"),
    pytest.param(ITEM_PRICE_MAX, id="at-max"),
]


@pytest.mark.unit
def test_when_only_name_given_then_new_item_uses_defaults():
    """when only a name is given, optional fields default and the item is active.

    Validates app.domain.entities.item.NewItem.__post_init__().
    """
    new_item = NewItem(name="Widget")

    assert new_item.description is None
    assert new_item.price is None
    assert new_item.is_active is True


@pytest.mark.unit
@pytest.mark.parametrize("name", VALID_NAMES)
def test_when_name_within_bounds_then_new_item_is_accepted(name):
    """when the name has 1 to 100 characters, the new item is accepted.

    Validates app.domain.entities.item.NewItem.__post_init__().
    """
    assert NewItem(name=name).name == name


@pytest.mark.unit
@pytest.mark.parametrize("name", INVALID_NAMES)
def test_when_name_blank_or_too_long_then_new_item_is_rejected(name):
    """when the name is blank or over 100 characters, validation fails.

    Validates app.domain.entities.item.NewItem.__post_init__().
    """
    with pytest.raises(DomainValidationError) as raised:
        NewItem(name=name)

    assert raised.value.log_context == {"field": "name"}


@pytest.mark.unit
@pytest.mark.parametrize("description", VALID_DESCRIPTIONS)
def test_when_description_within_bounds_then_new_item_is_accepted(description):
    """when the description has at most 500 characters, the item is accepted.

    Validates app.domain.entities.item.NewItem.__post_init__().
    """
    assert NewItem(name="Widget", description=description).description == description


@pytest.mark.unit
@pytest.mark.parametrize("description", INVALID_DESCRIPTIONS)
def test_when_description_too_long_then_new_item_is_rejected(description):
    """when the description has more than 500 characters, validation fails.

    Validates app.domain.entities.item.NewItem.__post_init__().
    """
    with pytest.raises(DomainValidationError) as raised:
        NewItem(name="Widget", description=description)

    assert raised.value.log_context == {"field": "description"}


@pytest.mark.unit
@pytest.mark.parametrize("price", VALID_PRICES)
def test_when_price_within_bounds_then_new_item_is_accepted(price):
    """when the price is between 0 and the maximum inclusive, the item is accepted.

    Validates app.domain.entities.item.NewItem.__post_init__().
    """
    assert NewItem(name="Widget", price=price).price == price


@pytest.mark.unit
@pytest.mark.parametrize("price", INVALID_PRICES)
def test_when_price_negative_or_not_finite_or_above_max_then_new_item_is_rejected(
    price,
):
    """when the price is negative, NaN, infinite or too large, validation fails.

    Validates app.domain.entities.item.NewItem.__post_init__().
    """
    with pytest.raises(DomainValidationError) as raised:
        NewItem(name="Widget", price=price)

    assert raised.value.log_context == {"field": "price"}


@pytest.mark.unit
def test_when_validation_fails_then_public_message_does_not_echo_the_input():
    """when a value is rejected, the public message does not repeat the input.

    Validates app.domain.entities.item.NewItem.__post_init__().
    """
    with pytest.raises(DomainValidationError) as raised:
        NewItem(name="Widget", description="leaked-text" * ITEM_DESCRIPTION_MAX_LENGTH)

    assert "leaked-text" not in raised.value.public_message


@pytest.mark.unit
def test_when_new_item_modified_then_frozen_error_is_raised():
    """when a field of a new item is assigned, the dataclass refuses it.

    Validates app.domain.entities.item.NewItem.
    """
    new_item = NewItem(name="Widget")

    with pytest.raises(FrozenInstanceError):
        new_item.name = "Other"  # type: ignore[misc]


@pytest.mark.unit
def test_when_stored_item_modified_then_frozen_error_is_raised():
    """when a field of a stored item is assigned, the dataclass refuses it.

    Validates app.domain.entities.item.Item.
    """
    item = make_item()

    with pytest.raises(FrozenInstanceError):
        item.name = "Other"  # type: ignore[misc]


@pytest.mark.unit
def test_when_no_field_given_then_changes_are_empty():
    """when nothing is set, every field is UNSET and no field is provided.

    Validates app.domain.entities.item.ItemChanges.provided_fields().
    """
    changes = ItemChanges()

    assert changes.name is UNSET
    assert changes.description is UNSET
    assert changes.price is UNSET
    assert changes.is_active is UNSET
    assert changes.provided_fields() == {}


@pytest.mark.unit
def test_when_none_given_for_optional_fields_then_they_are_provided_as_none():
    """when description and price are None, they are provided so they get cleared.

    Validates app.domain.entities.item.ItemChanges.provided_fields().
    """
    changes = ItemChanges(description=None, price=None)

    assert changes.provided_fields() == {"description": None, "price": None}


@pytest.mark.unit
def test_when_falsy_values_given_then_they_are_still_provided():
    """when is_active is False and price is 0, both count as provided.

    Validates app.domain.entities.item.ItemChanges.provided_fields().
    """
    changes = ItemChanges(is_active=False, price=0)

    assert changes.provided_fields() == {"is_active": False, "price": 0}


@pytest.mark.unit
def test_when_some_fields_given_then_only_those_are_provided():
    """when a subset is set, only that subset is provided.

    Validates app.domain.entities.item.ItemChanges.provided_fields().
    """
    changes = ItemChanges(name="Renamed", is_active=True)

    assert changes.provided_fields() == {"name": "Renamed", "is_active": True}


@pytest.mark.unit
@pytest.mark.parametrize("field", ["name", "is_active"])
def test_when_none_given_for_required_field_then_changes_are_rejected(field):
    """when name or is_active is None, validation fails because they cannot be cleared.

    Validates app.domain.entities.item.ItemChanges.__post_init__().
    """
    with pytest.raises(DomainValidationError) as raised:
        ItemChanges(**{field: None})

    assert raised.value.log_context == {"field": field}


@pytest.mark.unit
@pytest.mark.parametrize("name", INVALID_NAMES)
def test_when_changed_name_invalid_then_changes_are_rejected(name):
    """when the new name is blank or too long, validation fails.

    Validates app.domain.entities.item.ItemChanges.__post_init__().
    """
    with pytest.raises(DomainValidationError):
        ItemChanges(name=name)


@pytest.mark.unit
@pytest.mark.parametrize("name", VALID_NAMES)
def test_when_changed_name_within_bounds_then_changes_are_accepted(name):
    """when the new name has 1 to 100 characters, the changes are accepted.

    Validates app.domain.entities.item.ItemChanges.__post_init__().
    """
    assert ItemChanges(name=name).provided_fields() == {"name": name}


@pytest.mark.unit
@pytest.mark.parametrize("description", INVALID_DESCRIPTIONS)
def test_when_changed_description_too_long_then_changes_are_rejected(description):
    """when the new description is over 500 characters, validation fails.

    Validates app.domain.entities.item.ItemChanges.__post_init__().
    """
    with pytest.raises(DomainValidationError):
        ItemChanges(description=description)


@pytest.mark.unit
@pytest.mark.parametrize("description", VALID_DESCRIPTIONS)
def test_when_changed_description_within_bounds_then_changes_are_accepted(description):
    """when the new description has at most 500 characters, changes are accepted.

    Validates app.domain.entities.item.ItemChanges.__post_init__().
    """
    assert ItemChanges(description=description).description == description


@pytest.mark.unit
@pytest.mark.parametrize("price", INVALID_PRICES)
def test_when_changed_price_invalid_then_changes_are_rejected(price):
    """when the new price is negative, NaN, infinite or too large, validation fails.

    Validates app.domain.entities.item.ItemChanges.__post_init__().
    """
    with pytest.raises(DomainValidationError):
        ItemChanges(price=price)


@pytest.mark.unit
@pytest.mark.parametrize("price", VALID_PRICES)
def test_when_changed_price_within_bounds_then_changes_are_accepted(price):
    """when the new price is between 0 and the maximum, the changes are accepted.

    Validates app.domain.entities.item.ItemChanges.__post_init__().
    """
    assert ItemChanges(price=price).provided_fields() == {"price": price}


@pytest.mark.unit
def test_when_user_holds_a_requested_role_then_has_any_role_is_true():
    """when one of the requested roles is held, has_any_role is True.

    Validates app.domain.entities.authenticated_user.AuthenticatedUser.has_any_role().
    """
    assert TEST_USER.has_any_role(["admin", "tester"]) is True


@pytest.mark.unit
def test_when_user_holds_none_of_the_roles_then_has_any_role_is_false():
    """when none of the requested roles is held, has_any_role is False.

    Validates app.domain.entities.authenticated_user.AuthenticatedUser.has_any_role().
    """
    assert TEST_USER.has_any_role(["admin", "auditor"]) is False


@pytest.mark.unit
def test_when_no_roles_requested_then_has_any_role_is_false():
    """when the requested roles are empty, nobody matches.

    Validates app.domain.entities.authenticated_user.AuthenticatedUser.has_any_role().
    """
    assert TEST_USER.has_any_role([]) is False


@pytest.mark.unit
def test_when_user_has_no_roles_then_has_any_role_is_false():
    """when the user holds no roles, no requested role matches.

    Validates app.domain.entities.authenticated_user.AuthenticatedUser.has_any_role().
    """
    user = AuthenticatedUser(id="anonymous", auth_method="development")

    assert user.roles == ()
    assert user.has_any_role(["tester"]) is False


@pytest.mark.unit
def test_when_roles_given_as_a_generator_then_has_any_role_consumes_it():
    """when the requested roles are a one-shot iterator, the result is still correct.

    Validates app.domain.entities.authenticated_user.AuthenticatedUser.has_any_role().
    """
    assert TEST_USER.has_any_role(role for role in ("tester",)) is True


@pytest.mark.unit
def test_when_authenticated_user_modified_then_frozen_error_is_raised():
    """when a field of an authenticated user is assigned, the dataclass refuses it.

    Validates app.domain.entities.authenticated_user.AuthenticatedUser.
    """
    with pytest.raises(FrozenInstanceError):
        TEST_USER.roles = ("admin",)  # type: ignore[misc]


@pytest.mark.unit
def test_when_fakes_checked_then_they_satisfy_the_domain_ports():
    """when the fakes are checked against the runtime-checkable ports, they conform.

    Validates app.domain.ports.item_repository.ItemRepositoryPort.
    """
    assert isinstance(FakeItemRepository(), ItemRepositoryPort)
    assert isinstance(FakeUnitOfWork(), UnitOfWorkPort)


@pytest.mark.unit
def test_when_object_lacks_the_port_methods_then_it_is_not_a_port():
    """when an object lacks the port methods, the conformance check fails.

    Validates app.domain.ports.item_repository.ItemRepositoryPort.
    """
    assert not isinstance(object(), ItemRepositoryPort)
    assert not isinstance(FakeUnitOfWork(), ItemRepositoryPort)
