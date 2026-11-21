"""Item DTOs: what ``ItemService`` returns, so domain entities stay inside."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.item import Item


@dataclass(frozen=True, slots=True)
class ItemDTO:
    """Read model of one item.

    Attributes:
        id: Identifier of the item.
        name: Display name.
        description: Optional free text.
        price: Optional unit price.
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

    @classmethod
    def from_entity(cls, item: Item) -> "ItemDTO":
        """Copy an entity into its read model.

        Args:
            item: The entity to copy.

        Returns:
            A DTO with the same field values.
        """
        return cls(
            id=item.id,
            name=item.name,
            description=item.description,
            price=item.price,
            is_active=item.is_active,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


@dataclass(frozen=True, slots=True)
class ItemPageDTO:
    """One page of items.

    Attributes:
        items: The items on this page, in listing order.
        total: Number of items across all pages.
    """

    items: tuple[ItemDTO, ...]
    total: int
