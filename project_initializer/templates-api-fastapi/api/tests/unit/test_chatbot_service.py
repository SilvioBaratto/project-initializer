"""Unit tests for the chat entities and ChatbotService, run against a fake model."""

from collections.abc import AsyncIterator
from dataclasses import FrozenInstanceError

import pytest

from app.application.dto.chatbot import (
    ChatAnswer,
    ChatQuery,
    ChatStreamChunk,
    ChatTurnDTO,
)
from app.application.services.chatbot_service import ChatbotService
from app.domain.entities.chat import ChatMessage, ChatRole
from app.domain.exceptions import DomainValidationError, ExternalServiceError
from app.domain.ports.chat_model import ChatModelPort
from tests.fakes import FakeChatModel

CONVERSATION = (
    ChatTurnDTO(role="user", content="Hello"),
    ChatTurnDTO(role="assistant", content="Hi, how can I help?"),
    ChatTurnDTO(role="user", content="What is your return policy?"),
)
UNKNOWN_ROLES = [
    pytest.param("system", id="system"),
    pytest.param("User", id="wrong-case"),
    pytest.param("", id="empty"),
    pytest.param("user ", id="trailing-space"),
]


async def _collect(chunks: AsyncIterator[ChatStreamChunk]) -> list[ChatStreamChunk]:
    return [chunk async for chunk in chunks]


@pytest.mark.unit
def test_when_chat_role_values_read_then_they_are_the_wire_names():
    """when the roles are read as strings, they are the lowercase wire names.

    Validates app.domain.entities.chat.ChatRole.
    """
    assert ChatRole.USER == "user"
    assert ChatRole.ASSISTANT == "assistant"
    assert ChatRole("assistant") is ChatRole.ASSISTANT


@pytest.mark.unit
def test_when_chat_message_modified_then_frozen_error_is_raised():
    """when a chat message field is assigned, the dataclass refuses it.

    Validates app.domain.entities.chat.ChatMessage.
    """
    message = ChatMessage(role=ChatRole.USER, content="Hello")

    with pytest.raises(FrozenInstanceError):
        message.content = "Other"  # type: ignore[misc]


@pytest.mark.unit
def test_when_query_built_without_history_then_history_is_empty():
    """when a query has no history, the history is an empty tuple.

    Validates app.application.dto.chatbot.ChatQuery.
    """
    assert ChatQuery(question="Hello").history == ()


@pytest.mark.unit
def test_when_fake_model_checked_then_it_satisfies_the_chat_model_port():
    """when the fake model is checked against the port, it conforms.

    Validates app.domain.ports.chat_model.ChatModelPort.
    """
    assert isinstance(FakeChatModel(), ChatModelPort)
    assert not isinstance(object(), ChatModelPort)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_when_question_asked_then_model_reply_is_returned():
    """when a question is asked, the model's complete reply is the answer.

    Validates app.application.services.chatbot_service.ChatbotService.answer().
    """
    chat_model = FakeChatModel(answer="We accept returns within 30 days.")
    service = ChatbotService(chat_model)

    answer = await service.answer(ChatQuery(question="Return policy?"))

    assert answer == ChatAnswer(answer="We accept returns within 30 days.")
    assert chat_model.last_question == "Return policy?"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_when_question_has_no_history_then_model_gets_empty_history():
    """when a query has no history, the model receives an empty history.

    Validates app.application.services.chatbot_service.ChatbotService.answer().
    """
    chat_model = FakeChatModel()

    await ChatbotService(chat_model).answer(ChatQuery(question="Hello"))

    assert list(chat_model.last_history or []) == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_when_history_given_then_turns_become_typed_messages_in_order():
    """when history is given, the model receives typed messages in the same order.

    Validates app.application.services.chatbot_service.ChatbotService.answer().
    """
    chat_model = FakeChatModel()

    await ChatbotService(chat_model).answer(
        ChatQuery(question="And shipping?", history=CONVERSATION)
    )

    assert list(chat_model.last_history or []) == [
        ChatMessage(role=ChatRole.USER, content="Hello"),
        ChatMessage(role=ChatRole.ASSISTANT, content="Hi, how can I help?"),
        ChatMessage(role=ChatRole.USER, content="What is your return policy?"),
    ]


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("role", UNKNOWN_ROLES)
async def test_when_history_role_unknown_then_validation_error_and_model_not_called(
    role,
):
    """when a history turn has an unknown role, validation fails before the model runs.

    Validates app.application.services.chatbot_service.ChatbotService.answer().
    """
    chat_model = FakeChatModel()
    query = ChatQuery(
        question="Hello", history=(ChatTurnDTO(role=role, content="text"),)
    )

    with pytest.raises(DomainValidationError) as raised:
        await ChatbotService(chat_model).answer(query)

    assert raised.value.public_message == "Unknown chat role"
    assert raised.value.log_context == {"role": role}
    assert chat_model.last_question is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_when_model_fails_then_external_service_error_propagates():
    """when the model raises ExternalServiceError, it reaches the caller unchanged.

    Validates app.application.services.chatbot_service.ChatbotService.answer().
    """
    failure = ExternalServiceError(log_context={"provider": "stub"})
    service = ChatbotService(FakeChatModel(error=failure))

    with pytest.raises(ExternalServiceError) as raised:
        await service.answer(ChatQuery(question="Hello"))

    assert raised.value is failure


@pytest.mark.unit
@pytest.mark.asyncio
async def test_when_answer_streamed_then_partials_precede_one_final_chunk():
    """when an answer is streamed, partial chunks come first and only the last is done.

    Validates app.application.services.chatbot_service.ChatbotService.stream_answer().
    """
    chat_model = FakeChatModel(answer="Hello there", partials=("Hel", "Hello"))
    service = ChatbotService(chat_model)

    chunks = await _collect(service.stream_answer(ChatQuery(question="Hi")))

    assert chunks == [
        ChatStreamChunk(content="Hel", done=False),
        ChatStreamChunk(content="Hello", done=False),
        ChatStreamChunk(content="Hello there", done=True),
    ]
    assert chat_model.last_question == "Hi"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_when_model_streams_no_partials_then_only_the_final_chunk_is_emitted():
    """when the model sends no partial text, only the final chunk is emitted.

    Validates app.application.services.chatbot_service.ChatbotService.stream_answer().
    """
    service = ChatbotService(FakeChatModel(answer="Done", partials=()))

    chunks = await _collect(service.stream_answer(ChatQuery(question="Hi")))

    assert chunks == [ChatStreamChunk(content="Done", done=True)]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_when_streaming_with_history_then_model_gets_typed_messages():
    """when streaming with history, the model receives typed messages in order.

    Validates app.application.services.chatbot_service.ChatbotService.stream_answer().
    """
    chat_model = FakeChatModel()
    service = ChatbotService(chat_model)

    await _collect(
        service.stream_answer(ChatQuery(question="Hi", history=CONVERSATION))
    )

    assert [message.role for message in chat_model.last_history or []] == [
        ChatRole.USER,
        ChatRole.ASSISTANT,
        ChatRole.USER,
    ]


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("role", UNKNOWN_ROLES)
async def test_when_streaming_with_unknown_role_then_validation_error_on_first_chunk(
    role,
):
    """when a streamed history has an unknown role, the first iteration fails.

    Validates app.application.services.chatbot_service.ChatbotService.stream_answer().
    """
    chat_model = FakeChatModel()
    query = ChatQuery(
        question="Hello", history=(ChatTurnDTO(role=role, content="text"),)
    )
    stream = ChatbotService(chat_model).stream_answer(query)

    with pytest.raises(DomainValidationError):
        await _collect(stream)

    assert chat_model.last_question is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_when_model_fails_while_streaming_then_error_propagates():
    """when the model fails during streaming, ExternalServiceError reaches the caller.

    Validates app.application.services.chatbot_service.ChatbotService.stream_answer().
    """
    service = ChatbotService(FakeChatModel(error=ExternalServiceError()))

    with pytest.raises(ExternalServiceError):
        await _collect(service.stream_answer(ChatQuery(question="Hi")))
