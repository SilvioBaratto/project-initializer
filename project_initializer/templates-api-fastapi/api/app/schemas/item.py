"""Item Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    """Base item schema with shared fields."""

    name: str = Field(..., min_length=1, max_length=100, description="Item name")
    description: Optional[str] = Field(
        default=None, max_length=500, description="Item description"
    )
    price: Optional[float] = Field(default=None, ge=0, description="Item price")
    is_active: bool = Field(default=True, description="Whether item is active")


class ItemCreate(ItemBase):
    """Schema for creating an item."""

    pass


class ItemUpdate(BaseModel):
    """Schema for updating an item (all fields optional)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    price: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class ItemResponse(ItemBase):
    """Schema for item responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Item ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ItemListResponse(BaseModel):
    """Schema for a list of items response."""

    items: List[ItemResponse]
    total: int = Field(..., description="Total number of items")
