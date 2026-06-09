"""User Pydantic schemas for request/response validation."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema with shared public fields."""

    email: EmailStr = Field(..., description="User email address")
    username: Optional[str] = Field(
        default=None, max_length=50, description="Optional username"
    )
    first_name: Optional[str] = Field(default=None, description="First name")
    last_name: Optional[str] = Field(default=None, description="Last name")
    is_active: bool = Field(default=True, description="Whether user is active")


class UserCreate(UserBase):
    """Schema for creating a user — includes plain-text password."""

    password: str = Field(..., min_length=8, description="Plain-text password (min 8 chars)")


class UserPublic(UserBase):
    """Schema for public user responses — never exposes credentials."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="User ID")


class UserInDB(UserPublic):
    """Internal schema that carries the stored password hash."""

    password_hash: str = Field(..., description="Hashed password (internal use only)")
