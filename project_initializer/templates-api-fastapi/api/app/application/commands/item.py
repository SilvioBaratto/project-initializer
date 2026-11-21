"""Item commands: the write intents the API layer hands to ``ItemService``."""

from dataclasses import dataclass

from app.domain.entities.item import UNSET, ItemChanges, NewItem, Unset


@dataclass(frozen=True, slots=True)
class CreateItemCommand:
    """Intent to create an item.

    Attributes:
        name: Display name.
        description: Optional free text.
        price: Optional unit price.
        is_active: Whether the item is offered from the start.
    """

    name: str
    description: str | None = None
    price: float | None = None
    is_active: bool = True

    def to_new_item(self) -> NewItem:
        """Convert to the validated domain input.

        Returns:
            The values as a ``NewItem``.

        Raises:
            DomainValidationError: A value breaks a business rule.
        """
        return NewItem(
            name=self.name,
            description=self.description,
            price=self.price,
            is_active=self.is_active,
        )


@dataclass(frozen=True, slots=True)
class UpdateItemCommand:
    """Intent to change an existing item; ``UNSET`` fields stay as they are.

    Attributes:
        item_id: Identifier of the item to change.
        name: New name.
        description: New description, or None to clear it.
        price: New price, or None to clear it.
        is_active: New active flag.
    """

    item_id: str
    name: str | Unset = UNSET
    description: str | None | Unset = UNSET
    price: float | None | Unset = UNSET
    is_active: bool | Unset = UNSET

    def to_changes(self) -> ItemChanges:
        """Convert to the validated domain input.

        Returns:
            The provided fields as an ``ItemChanges``.

        Raises:
            DomainValidationError: A provided value breaks a business rule.
        """
        return ItemChanges(
            name=self.name,
            description=self.description,
            price=self.price,
            is_active=self.is_active,
        )
