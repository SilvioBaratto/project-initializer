"""Composition root: wires concrete adapters into the application services.

This module builds the services that need a database session or an LLM client.
Routes ask for ``ItemServiceDep`` or ``ChatbotServiceDep`` and never build a
repository or a client themselves, which keeps them thin and lets tests swap any
adapter with ``app.dependency_overrides``.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.services.chatbot_service import ChatbotService
from app.application.services.item_service import ItemService
from app.domain.ports.chat_model import ChatModelPort
from app.infrastructure.database import get_db
from app.infrastructure.llm.baml_chat_model import BamlChatModel
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


@lru_cache(maxsize=1)
def get_chat_model() -> ChatModelPort:
    """Return the process-wide chat model.

    Cached because the BAML client is stateless and costly to build, and so tests
    can replace the whole dependency instead of patching the client.

    Returns:
        The BAML-backed chat model.
    """
    return BamlChatModel()


def get_chatbot_service(
    chat_model: Annotated[ChatModelPort, Depends(get_chat_model)],
) -> ChatbotService:
    """Build the chatbot service for one request.

    Args:
        chat_model: The model that produces replies.

    Returns:
        A chatbot service over that model.
    """
    return ChatbotService(chat_model)


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
ChatbotServiceDep = Annotated[ChatbotService, Depends(get_chatbot_service)]
