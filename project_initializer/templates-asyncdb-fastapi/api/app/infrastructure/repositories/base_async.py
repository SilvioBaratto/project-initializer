"""Async twin of ``app/repositories/base.py`` for ``AsyncSession`` (opt-in).

Mirrors the sync ``BaseRepository`` CRUD shape using ``await session.execute``.
Only ``execute``/``flush``/``refresh``/``delete`` are awaited; ``session.add``
and the result accessors (``scalar_one_or_none``/``scalars().all()``) stay sync.
The service layer owns ``commit``; this repository only flushes.
"""

from typing import Any, Generic, Optional, Sequence, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.orm.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class AsyncBaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Generic async repository with CRUD operations over an ``AsyncSession``."""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get(self, id: Any) -> Optional[ModelType]:
        """Get a single record by ID."""
        stmt = select(self.model).where(getattr(self.model, "id") == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        desc: bool = True,
    ) -> Sequence[ModelType]:
        """Get multiple records with pagination, mirroring the sync repo."""
        stmt = self._ordered(select(self.model), order_by, desc)
        result = await self.session.execute(stmt.offset(skip).limit(limit))
        return result.scalars().all()

    def _ordered(self, stmt: Any, order_by: Optional[str], desc: bool) -> Any:
        """Apply the order_by column (or created_at fallback) to the statement."""
        name = order_by if order_by and hasattr(self.model, order_by) else None
        if name is None and hasattr(self.model, "created_at"):
            name = "created_at"
        if name is None:
            return stmt
        column = getattr(self.model, name)
        return stmt.order_by(column.desc() if desc else column.asc())

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record (flush only; service owns commit)."""
        db_obj = self.model(**obj_in.model_dump())
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(self, id: Any, obj_in: UpdateSchemaType) -> Optional[ModelType]:
        """Update an existing record, or return None if it does not exist."""
        db_obj = await self.get(id)
        if db_obj is None:
            return None
        for field, value in obj_in.model_dump(exclude_unset=True).items():
            setattr(db_obj, field, value)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: Any) -> bool:
        """Delete a record by ID, returning False if it does not exist."""
        db_obj = await self.get(id)
        if db_obj is None:
            return False
        await self.session.delete(db_obj)
        await self.session.flush()
        return True
