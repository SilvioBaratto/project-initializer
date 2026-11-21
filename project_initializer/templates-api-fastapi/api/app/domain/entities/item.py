"""Item entities and the business rules that keep their values valid.

``Item`` is the persisted shape the repository returns. ``NewItem`` and
``ItemChanges`` are the write inputs: they validate on construction, so an
invalid value can never reach a repository.
"""

import math
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from typing import Final

from app.domain.constants import (
    ITEM_DESCRIPTION_MAX_LENGTH,
    ITEM_NAME_MAX_LENGTH,
    ITEM_PRICE_MAX,
)
from app.domain.exceptions import DomainValidationError


class Unset(Enum):
    """Type of the ``UNSET`` sentinel, so type checkers can narrow on it."""

    UNSET = "UNSET"


# A partial update must tell "field not sent" apart from "field set to None"
# (which clears an optional field), so None cannot double as the marker.
UNSET: Final = Unset.UNSET


@dataclass(frozen=True, slots=True)
class Item:
    """A persisted item.

    Attributes:
        id: Opaque identifier assigned on creation.
        name: Display name.
        description: Optional free text.
        price: Optional unit price in the shop currency.
        is_active: Whether the item is currently offered.
        created_at: Creation time.
        updated_at: Time of the last change.
    """

    id: str
    name: str
    description: str | None
    price: float | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class NewItem:
    """Values for an item that does not exist yet.

    Attributes:
        name: Display name, 1 to ``ITEM_NAME_MAX_LENGTH`` characters and not blank.
        description: Optional text of at most ``ITEM_DESCRIPTION_MAX_LENGTH``
            characters.
        price: Optional finite price between 0 and ``ITEM_PRICE_MAX`` inclusive.
        is_active: Whether the item is offered from the start.

    Raises:
        DomainValidationError: On construction, when any value breaks its rule.
    """

    name: str
    description: str | None = None
    price: float | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        _validate_name(self.name)
        _validate_description(self.description)
        _validate_price(self.price)


@dataclass(frozen=True, slots=True)
class ItemChanges:
    """A partial update where every field defaults to ``UNSET`` (leave unchanged).

    ``description`` and ``price`` accept ``None`` to clear the stored value;
    ``name`` and ``is_active`` do not, because they are required on an item.

    Attributes:
        name: New name, under the same rules as ``NewItem.name``.
        description: New description, or ``None`` to clear it.
        price: New price, or ``None`` to clear it.
        is_active: New active flag.

    Raises:
        DomainValidationError: On construction, when a provided value breaks its
            rule or ``None`` is given for ``name`` or ``is_active``.
    """

    name: str | Unset = UNSET
    description: str | None | Unset = UNSET
    price: float | None | Unset = UNSET
    is_active: bool | Unset = UNSET

    def __post_init__(self) -> None:
        if self.name is not UNSET:
            _validate_name(self.name)
        if self.description is not UNSET:
            _validate_description(self.description)
        if self.price is not UNSET:
            _validate_price(self.price)
        if self.is_active is None:
            raise _invalid("is_active", "Item active flag cannot be cleared")

    def provided_fields(self) -> dict[str, object]:
        """Return the fields the caller set, keyed by field name.

        Returns:
            Only the fields that are not ``UNSET``. A field set to ``None`` is
            included, so the repository clears it. Empty when nothing changes.
        """
        values = {field.name: getattr(self, field.name) for field in fields(self)}
        return {name: value for name, value in values.items() if value is not UNSET}


def _invalid(field: str, message: str) -> DomainValidationError:
    return DomainValidationError(message, log_context={"field": field})


def _validate_name(name: str | None) -> None:
    if name is None or not name.strip():
        raise _invalid("name", "Item name must not be blank")
    if len(name) > ITEM_NAME_MAX_LENGTH:
        raise _invalid(
            "name", f"Item name must be at most {ITEM_NAME_MAX_LENGTH} characters"
        )


def _validate_description(description: str | None) -> None:
    if description is not None and len(description) > ITEM_DESCRIPTION_MAX_LENGTH:
        raise _invalid(
            "description",
            f"Item description must be at most {ITEM_DESCRIPTION_MAX_LENGTH} "
            "characters",
        )


def _validate_price(price: float | None) -> None:
    if price is None:
        return
    if not (math.isfinite(price) and 0 <= price <= ITEM_PRICE_MAX):
        raise _invalid(
            "price",
            f"Item price must be a number between 0 and {ITEM_PRICE_MAX:,.0f}",
        )
