"""Chatbot use cases: answer a question, whole or streamed.

The service converts API-facing turns into domain messages and delegates to a
``ChatModelPort``, so no LLM client is imported here and unit tests run against
a fake model.
"""

from collections.abc import AsyncIterator, Sequence

from app.application.dto.chatbot import (
    ChatAnswer,
    ChatQuery,
    ChatStreamChunk,
    ChatTurnDTO,
)
from app.domain.entities.chat import ChatMessage, ChatRole
from app.domain.exceptions import DomainValidationError
from app.domain.ports.chat_model import ChatModelPort


class ChatbotService:
    """Orchestrates chatbot use cases over a ``ChatModelPort``."""

    def __init__(self, chat_model: ChatModelPort) -> None:
        """Wire the service.

        Args:
            chat_model: The model that produces replies.
        """
        self._chat_model = chat_model

    async def answer(self, query: ChatQuery) -> ChatAnswer:
        """Answer a question in one piece.

        Args:
            query: The question and the conversation so far.

        Returns:
            The complete reply.

        Raises:
            DomainValidationError: A history turn has an unknown role.
            ExternalServiceError: The model could not produce a reply.
        """
        reply = await self._chat_model.complete(
            query.question, _to_messages(query.history)
        )
        return ChatAnswer(answer=reply)

    async def stream_answer(self, query: ChatQuery) -> AsyncIterator[ChatStreamChunk]:
        """Answer a question incrementally.

        Validation and model errors surface on the first iteration, not at call
        time, because this is an async generator.

        Args:
            query: The question and the conversation so far.

        Yields:
            Partial chunks, then one chunk with ``done`` set.

        Raises:
            DomainValidationError: A history turn has an unknown role.
            ExternalServiceError: The model failed before or during streaming.
        """
        history = _to_messages(query.history)
        async for chunk in self._chat_model.stream(query.question, history):
            yield ChatStreamChunk(content=chunk.content, done=chunk.is_final)


def _to_messages(history: Sequence[ChatTurnDTO]) -> list[ChatMessage]:
    return [ChatMessage(role=_to_role(turn), content=turn.content) for turn in history]


def _to_role(turn: ChatTurnDTO) -> ChatRole:
    try:
        return ChatRole(turn.role)
    except ValueError:
        # The role string came from the client, so it is logged but not echoed.
        raise DomainValidationError(
            "Unknown chat role", log_context={"role": turn.role}
        ) from None
