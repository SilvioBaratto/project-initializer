"""
Schemas Package
===============

This package contains Pydantic models for request/response validation and serialization.

File Structure
--------------
schemas/
├── __init__.py       # This file - exports all schemas
├── base.py           # Common base schemas and mixins
└── <entity>.py       # Entity-specific schemas (user.py, item.py, etc.)

Schema Naming Conventions
-------------------------
For each entity, create these schema types:
- <Entity>Base     - Shared fields between create/update
- <Entity>Create   - Fields required for creation
- <Entity>Update   - Fields for updates (all optional)
- <Entity>Response - Fields returned in responses
- <Entity>InDB     - Database representation (includes DB-only fields)

Example Schema Organization
---------------------------
```python
# schemas/user.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class UserBase(BaseModel):
    \"\"\"Base schema with shared fields.\"\"\"
    email: EmailStr = Field(..., description="User email address")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")
    is_active: bool = Field(True, description="Whether user is active")


class UserCreate(UserBase):
    \"\"\"Schema for creating a new user.\"\"\"
    password: str = Field(..., min_length=8, description="User password")


class UserUpdate(BaseModel):
    \"\"\"Schema for updating a user. All fields optional.\"\"\"
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    \"\"\"Schema for user responses.\"\"\"
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class UserInDB(UserResponse):
    \"\"\"Schema with DB-only fields (internal use).\"\"\"
    hashed_password: str
```

Common Schema Patterns
----------------------
```python
# schemas/base.py
from datetime import datetime, timezone
from typing import Optional, Generic, TypeVar, List
from pydantic import BaseModel, Field, ConfigDict

DataT = TypeVar("DataT")


class TimestampSchema(BaseModel):
    \"\"\"Mixin for timestamp fields.\"\"\"
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel, Generic[DataT]):
    \"\"\"Generic paginated response schema.\"\"\"
    items: List[DataT]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")


class ErrorResponse(BaseModel):
    \"\"\"Standard error response.\"\"\"
    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Error details")
    code: Optional[str] = Field(None, description="Error code")


class SuccessResponse(BaseModel):
    \"\"\"Standard success response.\"\"\"
    success: bool = True
    message: Optional[str] = None


# Validators example
from pydantic import field_validator

class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        return v
```

Best Practices
--------------
1. **Use Field()**: Always use Field() for validation and documentation
2. **ConfigDict**: Use model_config = ConfigDict(from_attributes=True) for ORM
3. **Separate Create/Update**: Different validation needs for each operation
4. **Optional Updates**: All fields in Update schemas should be Optional
5. **EmailStr**: Use EmailStr for email validation
6. **Datetime Handling**: Use timezone-aware datetimes
7. **Validators**: Use @field_validator for custom validation
8. **Documentation**: Field descriptions appear in OpenAPI docs
9. **Generic Responses**: Use generics for paginated responses
10. **Nested Schemas**: Compose schemas for complex responses
"""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.chatbot import (
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    StreamChunk,
)
from app.schemas.item import (
    ItemBase,
    ItemCreate,
    ItemListResponse,
    ItemResponse,
    ItemUpdate,
)
from app.schemas.user import (
    UserBase,
    UserCreate,
    UserInDB,
    UserPublic,
)


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


# ===========================
# Message/Echo Schemas
# ===========================


class MessageResponse(BaseModel):
    """Simple message response"""

    message: str


class EchoRequest(BaseModel):
    """Echo request body"""

    message: str = Field(..., description="Message to echo back")
    metadata: Optional[dict] = Field(default=None, description="Optional metadata")


class EchoResponse(BaseModel):
    """Echo response"""

    echo: str
    received_at: datetime = Field(default_factory=utc_now)
    metadata: Optional[dict] = None


# ===========================
# Item CRUD Schemas
# ===========================
# Item schemas live in app/schemas/item.py and are re-exported above so that
# `from app.schemas import ItemCreate` continues to resolve.


# ===========================
# Generic API Schemas
# ===========================


class ErrorResponse(BaseModel):
    """Standard error response"""

    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class SuccessResponse(BaseModel):
    """Standard success response"""

    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None


# Export all schemas
__all__ = [
    "utc_now",
    "MessageResponse",
    "EchoRequest",
    "EchoResponse",
    "ItemBase",
    "ItemCreate",
    "ItemUpdate",
    "ItemResponse",
    "ItemListResponse",
    "ErrorResponse",
    "SuccessResponse",
    "ConversationHistory",
    "ChatRequest",
    "ChatResponse",
    "StreamChunk",
    "UserBase",
    "UserCreate",
    "UserPublic",
    "UserInDB",
]
