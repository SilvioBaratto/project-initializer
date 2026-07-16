"""Item domain entity — a framework-free business object.

Deliberately a plain dataclass with no SQLAlchemy/Pydantic/FastAPI imports: the
domain layer owns this shape, and the infrastructure repository maps its ORM
rows onto it. Pydantic response models read it via ``from_attributes`` at the
API edge, so the same attribute names flow straight through to the HTTP schema.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Item:
    """A persisted item in the domain's terms."""

    id: str
    name: str
    description: Optional[str]
    price: Optional[float]
    is_active: bool
    created_at: datetime
    updated_at: datetime
