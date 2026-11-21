"""Chat request and response models.

The wire format is stable: clients send the history as ``"role: text"`` strings
and the API turns them into typed turns before the application layer sees them.
"""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.application.dto.chatbot import ChatQuery, ChatTurnDTO
from app.domain.constants import (
    CHAT_HISTORY_MAX_MESSAGES,
    CHAT_MESSAGE_MAX_LENGTH,
    CHAT_QUESTION_MAX_LENGTH,
)
from app.domain.entities.chat import ChatRole

# Matched case-insensitively because browsers and scripts capitalise the role.
_ROLE_PREFIXES: tuple[tuple[str, ChatRole], ...] = (
    (f"{ChatRole.USER.value}:", ChatRole.USER),
    (f"{ChatRole.ASSISTANT.value}:", ChatRole.ASSISTANT),
)

HistoryMessage = Annotated[str, Field(max_length=CHAT_MESSAGE_MAX_LENGTH)]
# Stripped before the length check, so a question of only blanks is refused
# instead of being sent to a paid model.
UserQuestion = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=CHAT_QUESTION_MAX_LENGTH
    ),
]


def _parse_turn(message: str) -> ChatTurnDTO:
    for prefix, role in _ROLE_PREFIXES:
        if message[: len(prefix)].lower() == prefix:
            return ChatTurnDTO(role=role.value, content=message[len(prefix) :].strip())
    return ChatTurnDTO(role=ChatRole.USER.value, content=message)


class ConversationHistory(BaseModel):
    """Earlier turns of the conversation, oldest first.

    Attributes:
        messages: One string per turn, written ``"user: text"`` or
            ``"assistant: text"``. A string with neither prefix counts as a
            user turn.
    """

    messages: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=CHAT_HISTORY_MAX_MESSAGES,
        description="Previous turns written as 'user: text' or 'assistant: text'",
    )

    def to_turns(self) -> tuple[ChatTurnDTO, ...]:
        """Parse the strings into typed turns.

        Returns:
            One turn per message, with a lower-case role name as the application
            layer expects.
        """
        return tuple(_parse_turn(message) for message in self.messages)


class ChatRequest(BaseModel):
    """Body of the chat routes.

    Attributes:
        user_question: The user's latest message, without surrounding
            whitespace; it must hold at least one other character.
        conversation_history: Earlier turns, for context.
    """

    user_question: UserQuestion = Field(
        description="The user's question or message",
        examples=["What can this API do?"],
    )
    conversation_history: ConversationHistory | None = Field(
        default=None, description="Previous conversation messages for context"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"user_question": "What can this API do?"},
                {
                    "user_question": "Which routes are public?",
                    "conversation_history": {
                        "messages": [
                            "user: What can this API do?",
                            "assistant: It manages items and answers questions.",
                        ]
                    },
                },
            ]
        }
    }

    def to_query(self) -> ChatQuery:
        """Convert the body into the use-case query.

        Returns:
            The question together with the parsed history.
        """
        history = self.conversation_history
        return ChatQuery(
            question=self.user_question,
            history=history.to_turns() if history else (),
        )


class ChatResponse(BaseModel):
    """Body returned by ``POST /chat/``.

    Attributes:
        answer: The complete reply.
    """

    answer: str = Field(description="The chatbot's reply")


class StreamChunk(BaseModel):
    """One server-sent event of ``POST /chat/stream``.

    Attributes:
        content: Reply text carried by this chunk, or a generic failure message
            when ``error_code`` is set.
        done: True only for the last chunk, which holds the complete reply or the
            failure.
        error_code: Stable error code, present only on the last chunk of a stream
            that failed after it had started. A client tells a failed stream from
            a finished one by this field.
    """

    content: str = Field(description="Partial or complete reply text")
    done: bool = Field(default=False, description="Whether this is the final chunk")
    error_code: str | None = Field(
        default=None, description="Error code of a stream that failed midway"
    )
