"""Chat model port: the conversational LLM the chatbot use case depends on."""

from collections.abc import AsyncIterator, Sequence
from typing import Protocol, runtime_checkable

from app.domain.entities.chat import ChatMessage, ChatReplyChunk


@runtime_checkable
class ChatModelPort(Protocol):
    """Answers a question given the earlier turns of the conversation."""

    async def complete(self, question: str, history: Sequence[ChatMessage]) -> str:
        """Produce the full reply in one call.

        Args:
            question: The user's latest message.
            history: Earlier turns, oldest first. May be empty.

        Returns:
            The complete reply text.

        Raises:
            ExternalServiceError: The model provider failed or was unreachable.
        """
        ...

    def stream(
        self, question: str, history: Sequence[ChatMessage]
    ) -> AsyncIterator[ChatReplyChunk]:
        """Produce the reply incrementally.

        Implementations are async generators: calling this returns the iterator
        without starting the request, which starts on the first iteration.

        Args:
            question: The user's latest message.
            history: Earlier turns, oldest first. May be empty.

        Returns:
            An iterator of partial chunks ending with one chunk whose
            ``is_final`` is True.

        Raises:
            ExternalServiceError: The model provider failed or was unreachable,
                raised while iterating.
        """
        ...
