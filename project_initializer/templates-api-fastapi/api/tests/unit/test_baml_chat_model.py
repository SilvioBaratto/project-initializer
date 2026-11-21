"""Unit tests for the BAML chat model adapter, run against a fake BAML client."""

import inspect
import logging
import os
import traceback
from collections.abc import AsyncIterator, Callable
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from baml_py.errors import (
    BamlClientFinishReasonError,
    BamlClientHttpError,
    BamlError,
    BamlTimeoutError,
    BamlValidationError,
)

from app.domain.entities.chat import ChatMessage, ChatReplyChunk, ChatRole
from app.domain.exceptions import ExternalServiceError
from app.infrastructure.llm.baml_chat_model import (
    BAML_LOG_ENVIRONMENT_VARIABLE,
    BAML_LOG_OFF,
    BamlChatModel,
)
from baml_client.async_client import BamlAsyncClient, BamlStreamClient
from baml_client.types import ChatTurn

pytestmark = pytest.mark.unit

PROVIDER_SECRET = "sk-live-0123456789 from https://internal.example/openai"
USER_PROMPT = "my email is jane@example.com, what is my balance?"
RAW_REPLY = "raw provider reply that mentions jane@example.com"
CLIENT_NAME = "AzureOpenAI"
LEAKABLE_TEXTS = (PROVIDER_SECRET, USER_PROMPT, RAW_REPLY)

HISTORY = (
    ChatMessage(ChatRole.USER, "What is Python?"),
    ChatMessage(ChatRole.ASSISTANT, "A programming language."),
)


class FakeBamlStream:
    """Mimics ``baml_py.BamlStream``: async iteration, then a final response."""

    def __init__(
        self,
        partials: list[str | None],
        final: str,
        *,
        iteration_error: BamlError | None = None,
        final_error: BamlError | None = None,
    ) -> None:
        self._partials = partials
        self._final = final
        self._iteration_error = iteration_error
        self._final_error = final_error

    def __aiter__(self) -> AsyncIterator[SimpleNamespace]:
        return self._partial_responses()

    async def _partial_responses(self) -> AsyncIterator[SimpleNamespace]:
        for answer in self._partials:
            yield SimpleNamespace(answer=answer)
        if self._iteration_error is not None:
            raise self._iteration_error

    async def get_final_response(self) -> SimpleNamespace:
        """Return the complete reply, or raise the configured failure."""
        if self._final_error is not None:
            raise self._final_error
        return SimpleNamespace(answer=self._final)


class FakeBamlClient:
    """Stands in for the generated ``BamlAsyncClient``; records its calls."""

    def __init__(
        self,
        *,
        answer: str = "stub answer",
        call_error: Exception | None = None,
        baml_stream: FakeBamlStream | None = None,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self._answer = answer
        self._call_error = call_error
        self._baml_stream = baml_stream or FakeBamlStream([], "")
        self.stream = SimpleNamespace(Chat=self._start_stream)

    # The name mirrors the method BAML generates for the ``Chat`` function.
    async def Chat(  # noqa: N802
        self, user_question: str, history: list[object]
    ) -> SimpleNamespace:
        """Record the call and return the configured answer or raise the failure."""
        self.calls.append({"user_question": user_question, "history": history})
        if self._call_error is not None:
            raise self._call_error
        return SimpleNamespace(answer=self._answer)

    def _start_stream(
        self, user_question: str, history: list[object]
    ) -> FakeBamlStream:
        self.calls.append({"user_question": user_question, "history": history})
        return self._baml_stream


def _model(client: FakeBamlClient) -> BamlChatModel:
    return BamlChatModel(client)  # type: ignore[arg-type]


async def _collect(model: BamlChatModel, question: str = "q") -> list[ChatReplyChunk]:
    return [chunk async for chunk in model.stream(question, HISTORY)]


def _roles_and_contents(call: dict[str, object]) -> list[tuple[str, str]]:
    return [(turn.role, turn.content) for turn in call["history"]]  # type: ignore[attr-defined]


def _required_parameters(function: Callable[..., object]) -> set[str]:
    return {
        name
        for name, parameter in inspect.signature(function).parameters.items()
        if name != "self" and parameter.default is inspect.Parameter.empty
    }


# Each factory builds a fresh exception so a raised instance is never reused. The
# prompt, the raw reply and the provider's message go into the constructors the
# way the real runtime fills them.
BAML_FAILURES = [
    pytest.param(
        lambda: BamlClientHttpError(
            CLIENT_NAME,
            PROVIDER_SECRET,
            HTTPStatus.SERVICE_UNAVAILABLE,
            PROVIDER_SECRET,
        ),
        {
            "error_type": "BamlClientHttpError",
            "client_name": CLIENT_NAME,
            "status_code": HTTPStatus.SERVICE_UNAVAILABLE,
        },
        id="http",
    ),
    pytest.param(
        lambda: BamlClientFinishReasonError(
            USER_PROMPT, PROVIDER_SECRET, RAW_REPLY, "length", PROVIDER_SECRET
        ),
        {"error_type": "BamlClientFinishReasonError", "finish_reason": "length"},
        id="finish-reason",
    ),
    pytest.param(
        lambda: BamlValidationError(
            USER_PROMPT, PROVIDER_SECRET, RAW_REPLY, PROVIDER_SECRET
        ),
        {"error_type": "BamlValidationError"},
        id="validation",
    ),
    pytest.param(
        lambda: BamlTimeoutError(CLIENT_NAME, PROVIDER_SECRET),
        {"error_type": "BamlTimeoutError", "client_name": CLIENT_NAME},
        id="timeout",
    ),
    pytest.param(
        lambda: BamlError(PROVIDER_SECRET),
        {"error_type": "BamlError"},
        id="generic",
    ),
]


BAML_ERROR_FACTORIES = [
    pytest.param(case.values[0], id=case.id) for case in BAML_FAILURES
]


@pytest.fixture
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """An empty stand-in for ``os.environ`` that is dropped after the test."""
    environment: dict[str, str] = {}
    monkeypatch.setattr(os, "environ", environment)
    return environment


def _rendered(error: BaseException) -> str:
    return "".join(
        (
            "".join(traceback.format_exception(error)),
            str(error),
            repr(error),
            repr(getattr(error, "log_context", None)),
        )
    )


async def test_when_complete_succeeds_then_it_returns_the_reply_text() -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.complete()."""
    client = FakeBamlClient(answer="Paris")

    answer = await _model(client).complete("Capital of France?", ())

    assert answer == "Paris"
    assert client.calls[0]["user_question"] == "Capital of France?"


async def test_when_complete_has_history_then_it_maps_it_to_typed_turns() -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.complete()."""
    client = FakeBamlClient()

    await _model(client).complete("And Java?", HISTORY)

    assert _roles_and_contents(client.calls[0]) == [
        ("user", "What is Python?"),
        ("assistant", "A programming language."),
    ]


async def test_when_complete_has_no_history_then_it_sends_an_empty_list() -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.complete()."""
    client = FakeBamlClient()

    await _model(client).complete("hi", ())

    assert client.calls[0]["history"] == []


async def test_when_complete_calls_baml_then_it_passes_generated_parameters() -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.complete().

    Compared with the generated client's signature, so renaming a parameter in
    ``baml_src`` fails here instead of at the first real request.
    """
    client = FakeBamlClient()

    await _model(client).complete("q", HISTORY)

    assert set(client.calls[0]) == _required_parameters(BamlAsyncClient.Chat)


async def test_when_stream_calls_baml_then_it_passes_the_generated_parameters() -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.stream()."""
    client = FakeBamlClient(baml_stream=FakeBamlStream([], "done"))

    await _collect(_model(client))

    assert set(client.calls[0]) == _required_parameters(BamlStreamClient.Chat)


def test_when_the_turn_type_is_generated_then_it_has_the_adapter_fields() -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel."""
    assert set(ChatTurn.model_fields) == {"role", "content"}


@pytest.mark.parametrize("role", list(ChatRole))
def test_when_a_chat_role_is_sent_then_the_generated_turn_type_accepts_it(
    role: ChatRole,
) -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel."""
    assert ChatTurn(role=role.value, content="x").role == role.value


@pytest.mark.parametrize(("make_error", "expected_context"), BAML_FAILURES)
async def test_when_complete_fails_then_the_error_carries_only_safe_context(
    make_error: Callable[[], BamlError],
    expected_context: dict[str, object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.complete()."""
    model = _model(FakeBamlClient(call_error=make_error()))

    with caplog.at_level(logging.DEBUG), pytest.raises(ExternalServiceError) as raised:
        await model.complete(USER_PROMPT, HISTORY)

    error = raised.value
    assert error.log_context == {"operation": "complete", **expected_context}
    assert error.public_message == ExternalServiceError.default_message
    assert caplog.records == []


@pytest.mark.parametrize("make_error", BAML_ERROR_FACTORIES)
async def test_when_complete_fails_then_no_prompt_or_provider_text_survives(
    make_error: Callable[[], BamlError],
) -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.complete().

    A log handler renders the exception with its traceback, so the whole
    rendering is searched, not just the message.
    """
    model = _model(FakeBamlClient(call_error=make_error()))

    with pytest.raises(ExternalServiceError) as raised:
        await model.complete(USER_PROMPT, HISTORY)

    error = raised.value
    assert error.__cause__ is None
    assert error.__suppress_context__ is True
    rendered = _rendered(error)
    for text in LEAKABLE_TEXTS:
        assert text not in rendered


async def test_when_complete_raises_a_foreign_error_then_it_passes_through() -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.complete()."""
    model = _model(FakeBamlClient(call_error=RuntimeError("programming error")))

    with pytest.raises(RuntimeError, match="programming error"):
        await model.complete("hi", ())


async def test_when_stream_yields_partials_then_it_ends_with_a_final_chunk() -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.stream()."""
    client = FakeBamlClient(
        baml_stream=FakeBamlStream(["Hel", "Hello", "Hello wor"], "Hello world")
    )

    chunks = await _collect(_model(client))

    assert chunks == [
        ChatReplyChunk("Hel", is_final=False),
        ChatReplyChunk("Hello", is_final=False),
        ChatReplyChunk("Hello wor", is_final=False),
        ChatReplyChunk("Hello world", is_final=True),
    ]


async def test_when_a_partial_is_empty_then_stream_skips_it() -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.stream()."""
    client = FakeBamlClient(baml_stream=FakeBamlStream([None, "", "Hi"], "Hi there"))

    chunks = await _collect(_model(client))

    assert [chunk.content for chunk in chunks] == ["Hi", "Hi there"]


async def test_when_stream_has_history_then_it_maps_it_to_typed_turns() -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.stream()."""
    client = FakeBamlClient(baml_stream=FakeBamlStream([], "done"))

    await _collect(_model(client), "next question")

    assert client.calls[0]["user_question"] == "next question"
    assert _roles_and_contents(client.calls[0]) == [
        ("user", "What is Python?"),
        ("assistant", "A programming language."),
    ]


async def test_when_the_stream_fails_midway_then_the_error_is_safe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.stream()."""
    failure = BamlValidationError(
        USER_PROMPT, PROVIDER_SECRET, RAW_REPLY, PROVIDER_SECRET
    )
    client = FakeBamlClient(
        baml_stream=FakeBamlStream(["partial"], "", iteration_error=failure)
    )
    received: list[ChatReplyChunk] = []

    with caplog.at_level(logging.DEBUG), pytest.raises(ExternalServiceError) as raised:
        async for chunk in _model(client).stream("q", HISTORY):
            received.append(chunk)

    assert [chunk.content for chunk in received] == ["partial"]
    assert raised.value.log_context == {
        "operation": "stream",
        "error_type": "BamlValidationError",
    }
    assert caplog.records == []
    for text in LEAKABLE_TEXTS:
        assert text not in _rendered(raised.value)


async def test_when_the_final_response_fails_then_stream_raises_a_safe_error() -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.stream()."""
    failure = BamlClientHttpError(
        CLIENT_NAME, PROVIDER_SECRET, HTTPStatus.BAD_GATEWAY, RAW_REPLY
    )
    client = FakeBamlClient(baml_stream=FakeBamlStream(["x"], "", final_error=failure))

    with pytest.raises(ExternalServiceError) as raised:
        await _collect(_model(client))

    assert raised.value.public_message == ExternalServiceError.default_message
    assert raised.value.log_context == {
        "operation": "stream",
        "error_type": "BamlClientHttpError",
        "client_name": CLIENT_NAME,
        "status_code": HTTPStatus.BAD_GATEWAY,
    }
    for text in LEAKABLE_TEXTS:
        assert text not in _rendered(raised.value)


def test_when_baml_log_is_unset_then_the_adapter_turns_baml_logging_off(
    isolated_environment: dict[str, str],
) -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel.

    BAML prints every prompt and reply to stdout at its default level, so the
    adapter defaults the library's own logging to off.
    """
    _model(FakeBamlClient())

    assert isolated_environment[BAML_LOG_ENVIRONMENT_VARIABLE] == BAML_LOG_OFF


def test_when_baml_log_is_set_then_the_adapter_keeps_the_operator_choice(
    isolated_environment: dict[str, str],
) -> None:
    """Validates app.infrastructure.llm.baml_chat_model.BamlChatModel."""
    isolated_environment[BAML_LOG_ENVIRONMENT_VARIABLE] = "info"

    _model(FakeBamlClient())

    assert isolated_environment[BAML_LOG_ENVIRONMENT_VARIABLE] == "info"
