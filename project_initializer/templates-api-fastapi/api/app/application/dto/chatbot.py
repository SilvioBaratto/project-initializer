"""Chatbot DTOs: the contract between the API layer and ``ChatbotService``."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChatTurnDTO:
    """One earlier turn of the conversation.

    Attributes:
        role: ``"user"`` or ``"assistant"``; the service rejects anything else.
        content: Message text.
    """

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ChatQuery:
    """A question together with the conversation so far.

    Attributes:
        question: The user's latest message.
        history: Earlier turns, oldest first.
    """

    question: str
    history: tuple[ChatTurnDTO, ...] = ()


@dataclass(frozen=True, slots=True)
class ChatAnswer:
    """A complete reply.

    Attributes:
        answer: Reply text.
    """

    answer: str


@dataclass(frozen=True, slots=True)
class ChatStreamChunk:
    """One piece of a streamed reply.

    Attributes:
        content: Reply text carried by this chunk.
        done: True only for the last chunk, whose content is the complete reply.
    """

    content: str
    done: bool
