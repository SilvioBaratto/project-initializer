"""Chat conversation entities exchanged with a chat model."""

from dataclasses import dataclass
from enum import StrEnum


class ChatRole(StrEnum):
    """Author of a chat message. The values are the wire names."""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One turn of the conversation history.

    Attributes:
        role: Who wrote the message.
        content: Message text.
    """

    role: ChatRole
    content: str


@dataclass(frozen=True, slots=True)
class ChatReplyChunk:
    """One piece of a streamed reply.

    Attributes:
        content: Reply text carried by this chunk.
        is_final: True only for the last chunk, whose content is the complete
            reply rather than a partial one.
    """

    content: str
    is_final: bool
