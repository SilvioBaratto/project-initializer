"""Composition root: wires concrete adapters into the application services.

This module builds the services that need a database session. Routes ask for
``ItemServiceDep`` and never build a repository themselves, which keeps them thin
and lets tests swap any adapter with ``app.dependency_overrides``.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.services.item_service import ItemService
from app.infrastructure.database import get_db
from app.infrastructure.repositories.item import SqlAlchemyItemRepository
from app.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


def get_item_service(session: Annotated[Session, Depends(get_db)]) -> ItemService:
    """Build the item service for one request.

    The repository and the unit of work share the request's session, so the
    service's commit covers exactly the writes the repository staged.

    Args:
        session: Database session of the request.

    Returns:
        An item service bound to that session.
    """
    return ItemService(SqlAlchemyItemRepository(session), SqlAlchemyUnitOfWork(session))


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
