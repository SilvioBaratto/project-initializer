"""
Base Repository Module
======================

Generic base repository providing common CRUD operations for all entities.
Uses SQLAlchemy 2.0+ synchronous patterns with proper type hints.
"""

from typing import Generic, TypeVar, Optional, Sequence, Any, Type
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models.base import Base


ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Generic repository with CRUD operations.

    Type Parameters:
        ModelType: SQLAlchemy model class
        CreateSchemaType: Pydantic schema for creation
        UpdateSchemaType: Pydantic schema for updates

    Usage:
        class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
            def __init__(self, session: Session):
                super().__init__(User, session)
    """

    def __init__(self, model: Type[ModelType], session: Session):
        self.model = model
        self.session = session

    def get(self, id: Any) -> Optional[ModelType]:
        """Get a single record by ID."""
        id_column = getattr(self.model, "id")
        stmt = select(self.model).where(id_column == id)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def get_by_field(self, field: str, value: Any) -> Optional[ModelType]:
        """Get a single record by any field."""
        column = getattr(self.model, field)
        stmt = select(self.model).where(column == value)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        desc: bool = True
    ) -> Sequence[ModelType]:
        """Get multiple records with pagination."""
        stmt = select(self.model)

        if order_by and hasattr(self.model, order_by):
            column = getattr(self.model, order_by)
            stmt = stmt.order_by(column.desc() if desc else column.asc())
        elif hasattr(self.model, "created_at"):
            column = getattr(self.model, "created_at")
            stmt = stmt.order_by(column.desc() if desc else column.asc())

        stmt = stmt.offset(skip).limit(limit)
        result = self.session.execute(stmt)
        return result.scalars().all()

    def get_all(self) -> Sequence[ModelType]:
        """Get all records (use with caution on large tables)."""
        stmt = select(self.model)
        result = self.session.execute(stmt)
        return result.scalars().all()

    def create(self, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        obj_data = obj_in.model_dump()
        db_obj = self.model(**obj_data)
        self.session.add(db_obj)
        self.session.flush()
        self.session.refresh(db_obj)
        return db_obj

    def create_from_dict(self, obj_data: dict) -> ModelType:
        """Create a new record from dictionary."""
        db_obj = self.model(**obj_data)
        self.session.add(db_obj)
        self.session.flush()
        self.session.refresh(db_obj)
        return db_obj

    def update(self, id: Any, obj_in: UpdateSchemaType) -> Optional[ModelType]:
        """Update an existing record."""
        db_obj = self.get(id)
        if not db_obj:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        self.session.flush()
        self.session.refresh(db_obj)
        return db_obj

    def update_from_dict(self, id: Any, obj_data: dict) -> Optional[ModelType]:
        """Update an existing record from dictionary."""
        db_obj = self.get(id)
        if not db_obj:
            return None

        for field, value in obj_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        self.session.flush()
        self.session.refresh(db_obj)
        return db_obj

    def delete(self, id: Any) -> bool:
        """Delete a record by ID."""
        db_obj = self.get(id)
        if not db_obj:
            return False
        self.session.delete(db_obj)
        self.session.flush()
        return True

    def count(self) -> int:
        """Count total records."""
        stmt = select(func.count()).select_from(self.model)
        result = self.session.execute(stmt)
        return result.scalar_one()

    def exists(self, id: Any) -> bool:
        """Check if a record exists by ID."""
        id_column = getattr(self.model, "id")
        stmt = select(func.count()).where(id_column == id)
        result = self.session.execute(stmt)
        return result.scalar_one() > 0

    def exists_by_field(self, field: str, value: Any) -> bool:
        """Check if a record exists by field value."""
        column = getattr(self.model, field)
        stmt = select(func.count()).where(column == value)
        result = self.session.execute(stmt)
        return result.scalar_one() > 0
