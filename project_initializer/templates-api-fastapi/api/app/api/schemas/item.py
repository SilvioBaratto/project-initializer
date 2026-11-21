"""Item request and response models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.schemas.common import NulFreeStr
from app.application.commands.item import CreateItemCommand, UpdateItemCommand
from app.domain.constants import (
    ITEM_DESCRIPTION_MAX_LENGTH,
    ITEM_NAME_MAX_LENGTH,
    ITEM_PRICE_MAX,
)


class ItemBase(BaseModel):
    """Fields shared by the item request and response models.

    Attributes:
        name: Display name.
        description: Optional free text.
        price: Optional unit price. Money stays a float here, but it must be
            finite and within ``0..ITEM_PRICE_MAX``.
        is_active: Whether the item is offered.
    """

    name: NulFreeStr = Field(
        min_length=1,
        max_length=ITEM_NAME_MAX_LENGTH,
        description="Item name",
        examples=["Notebook"],
    )
    description: NulFreeStr | None = Field(
        default=None,
        max_length=ITEM_DESCRIPTION_MAX_LENGTH,
        description="Item description",
        examples=["A5 notebook, 80 pages"],
    )
    price: float | None = Field(
        default=None,
        ge=0,
        le=ITEM_PRICE_MAX,
        allow_inf_nan=False,
        description="Item price",
        examples=[4.5],
    )
    is_active: bool = Field(default=True, description="Whether the item is active")


class ItemCreate(ItemBase):
    """Body of ``POST /items``."""

    def to_command(self) -> CreateItemCommand:
        """Convert the request body into the use-case command.

        Returns:
            The command for ``ItemService.create_item``.
        """
        return CreateItemCommand(
            name=self.name,
            description=self.description,
            price=self.price,
            is_active=self.is_active,
        )


class ItemUpdate(BaseModel):
    """Body of ``PUT /items/{item_id}``; every field is optional.

    A field that is absent keeps its stored value, while an explicit ``null``
    clears the nullable ones (``description`` and ``price``). ``name`` and
    ``is_active`` cannot be cleared, so an explicit ``null`` there is refused. The
    distinction is what ``to_command`` preserves.
    """

    name: NulFreeStr | None = Field(
        default=None, min_length=1, max_length=ITEM_NAME_MAX_LENGTH, examples=["Pen"]
    )
    description: NulFreeStr | None = Field(
        default=None, max_length=ITEM_DESCRIPTION_MAX_LENGTH
    )
    price: float | None = Field(
        default=None, ge=0, le=ITEM_PRICE_MAX, allow_inf_nan=False, examples=[1.2]
    )
    is_active: bool | None = None

    @field_validator("name", "is_active")
    @classmethod
    def _refuse_explicit_null(cls, value: object) -> object:
        # Validators run only for a field the client sent, so an absent field
        # keeps its default None and still means "leave unchanged".
        if value is None:
            raise ValueError("must not be null")
        return value

    def to_command(self, item_id: str) -> UpdateItemCommand:
        """Convert the request body into the use-case command.

        Args:
            item_id: Identifier of the item to change, taken from the URL.

        Returns:
            A command that carries only the fields the client sent.
        """
        return UpdateItemCommand(item_id=item_id, **self.model_dump(exclude_unset=True))


class ItemResponse(ItemBase):
    """An item as returned to clients.

    Attributes:
        id: Item identifier.
        created_at: Creation time.
        updated_at: Time of the last change.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Item ID")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ItemListResponse(BaseModel):
    """One page of items.

    Attributes:
        items: The items of the requested page.
        total: Number of items across all pages.
    """

    model_config = ConfigDict(from_attributes=True)

    items: list[ItemResponse]
    total: int = Field(description="Total number of items")
