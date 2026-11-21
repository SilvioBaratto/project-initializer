"""Integration tests for the chat routes, run against a fake chat model.

No test reaches an LLM provider: ``get_chat_model`` is replaced, so the whole
route, service and error path is exercised deterministically.
"""

import json
import logging
from collections.abc import AsyncIterator, Callable, Sequence
from http import HTTPStatus
from typing import Any

import pytest

from app.api.deps import get_chat_model, get_chatbot_service
from app.api.handlers import INTERNAL_ERROR_CODE
from app.api.headers import RETRY_AFTER_HEADER
from app.api.v1.endpoints.chatbot import (
    STREAM_FAILED_LOG_MESSAGE,
    STREAM_FAILURE_MESSAGE,
)
from app.application.dto.chatbot import ChatQuery
from app.domain.constants import (
    CHAT_HISTORY_MAX_MESSAGES,
    CHAT_MESSAGE_MAX_LENGTH,
    CHAT_QUESTION_MAX_LENGTH,
)
from app.domain.entities.chat import ChatMessage, ChatReplyChunk, ChatRole
from app.domain.exceptions import ExternalServiceError
from app.main import app
from tests.fakes import FakeChatModel

pytestmark = pytest.mark.integration

QUESTION = "What can this API do?"
PROVIDER_DETAIL = "upstream node-7 rejected the request"
SSE_MEDIA_TYPE = "text/event-stream"
FIRST_PARTIAL = "Hel"
STREAM_LOGGER = "app.api.v1.endpoints.chatbot"
OUTAGE_ERROR_CODE = ExternalServiceError.error_code
INVALID_REQUESTS = [
    pytest.param({}, id="body-empty"),
    pytest.param({"user_question": ""}, id="question-empty"),
    pytest.param({"user_question": " \t\n "}, id="question-only-whitespace"),
    pytest.param(
        {"user_question": "q" * (CHAT_QUESTION_MAX_LENGTH + 1)}, id="question-too-long"
    ),
    pytest.param(
        {
            "user_question": QUESTION,
            "conversation_history": {
                "messages": ["user: hi"] * (CHAT_HISTORY_MAX_MESSAGES + 1)
            },
        },
        id="history-too-long",
    ),
    pytest.param(
        {
            "user_question": QUESTION,
            "conversation_history": {"messages": ["u" * (CHAT_MESSAGE_MAX_LENGTH + 1)]},
        },
        id="history-message-too-long",
    ),
]
CHAT_ROUTES = ["/chat/", "/chat/stream"]


class FailsAfterFirstPartial:
    """Chat model whose stream yields one partial reply and then raises."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def complete(self, question: str, history: Sequence[ChatMessage]) -> str:
        """Fail like the stream does."""
        raise self._error

    async def stream(
        self, question: str, history: Sequence[ChatMessage]
    ) -> AsyncIterator[ChatReplyChunk]:
        """Yield one partial chunk, then raise the configured error."""
        yield ChatReplyChunk(content=FIRST_PARTIAL, is_final=False)
        raise self._error


class SilentModel:
    """Chat model whose stream ends without producing a chunk."""

    async def complete(self, question: str, history: Sequence[ChatMessage]) -> str:
        """Return an empty reply."""
        return ""

    async def stream(
        self, question: str, history: Sequence[ChatMessage]
    ) -> AsyncIterator[ChatReplyChunk]:
        """End immediately."""
        return
        yield


@pytest.fixture
def install_chat_model(
    authenticated_client,
) -> Callable[[Any], Any]:
    """Replace the process-wide chat model with a fake for the current test.

    The override is dropped by the ``client`` fixture at teardown.
    """

    def install(model: Any) -> Any:
        """Serve ``model`` to the chat routes and return it for assertions."""
        app.dependency_overrides[get_chat_model] = lambda: model
        return model

    return install


@pytest.fixture
def chat_url(api_prefix: str) -> str:
    """URL of the complete-reply route."""
    return f"{api_prefix}/chat/"


@pytest.fixture
def stream_url(api_prefix: str) -> str:
    """URL of the streaming route."""
    return f"{api_prefix}/chat/stream"


def server_events(response) -> list[dict[str, Any]]:
    """Decode the ``data:`` events of a server-sent-event response body."""
    blocks = [block for block in response.text.split("\n\n") if block]
    return [json.loads(block.removeprefix("data: ")) for block in blocks]


def test_when_a_question_is_asked_then_the_models_answer_is_returned(
    authenticated_client, install_chat_model, chat_url
):
    """when a question is posted, 200 and the model's answer are returned.

    Validates app.api.v1.endpoints.chatbot.chat().
    """
    model = install_chat_model(FakeChatModel(answer="It manages items."))

    response = authenticated_client.post(chat_url, json={"user_question": QUESTION})

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"answer": "It manages items."}
    assert model.last_question == QUESTION
    assert list(model.last_history) == []


def test_when_history_is_sent_then_the_model_receives_typed_turns(
    authenticated_client, install_chat_model, chat_url
):
    """when history strings are posted, the model gets typed lower-case roles.

    A string without a role prefix counts as a user turn, and the prefix match
    ignores case.

    Validates app.api.schemas.chatbot.ConversationHistory.to_turns().
    """
    model = install_chat_model(FakeChatModel())
    history = ["user: hi", "ASSISTANT: hello", "no prefix at all"]

    authenticated_client.post(
        chat_url,
        json={
            "user_question": QUESTION,
            "conversation_history": {"messages": history},
        },
    )

    assert list(model.last_history) == [
        ChatMessage(ChatRole.USER, "hi"),
        ChatMessage(ChatRole.ASSISTANT, "hello"),
        ChatMessage(ChatRole.USER, "no prefix at all"),
    ]


def test_when_the_model_is_unavailable_then_503_hides_the_provider_detail(
    authenticated_client, install_chat_model, chat_url
):
    """when the model raises ExternalServiceError, the client gets a generic 503.

    The provider detail travels in the error's log context only.

    Validates app.api.handlers.handle_domain_error().
    """
    failure = ExternalServiceError(log_context={"provider": PROVIDER_DETAIL})
    install_chat_model(FakeChatModel(error=failure))

    response = authenticated_client.post(chat_url, json={"user_question": QUESTION})

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert PROVIDER_DETAIL not in response.text
    assert RETRY_AFTER_HEADER in response.headers


def test_when_the_model_crashes_then_500_carries_no_exception_text(
    authenticated_client, install_chat_model, chat_url
):
    """when the model raises an unexpected error, the 500 body is generic.

    The client re-raises server exceptions, so the catch-all middleware must
    answer without letting the exception escape.

    Validates app.api.middleware.unhandled_errors.UnhandledErrorMiddleware.
    """
    install_chat_model(FakeChatModel(error=RuntimeError(PROVIDER_DETAIL)))

    response = authenticated_client.post(chat_url, json={"user_question": QUESTION})

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert PROVIDER_DETAIL not in response.text
    assert "RuntimeError" not in response.text


@pytest.mark.parametrize("body", INVALID_REQUESTS)
def test_when_the_request_is_invalid_then_422_and_the_model_is_not_asked(
    authenticated_client, install_chat_model, chat_url, body
):
    """when the body breaks a bound, 422 is returned before the model is consulted.

    Validates app.api.schemas.chatbot.ChatRequest.
    """
    model = install_chat_model(FakeChatModel())

    response = authenticated_client.post(chat_url, json=body)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert model.last_question is None


@pytest.mark.parametrize(
    "limits",
    [
        pytest.param(
            {"user_question": "q" * CHAT_QUESTION_MAX_LENGTH}, id="question-at-limit"
        ),
        pytest.param(
            {
                "user_question": QUESTION,
                "conversation_history": {
                    "messages": ["m" * CHAT_MESSAGE_MAX_LENGTH]
                    * CHAT_HISTORY_MAX_MESSAGES
                },
            },
            id="history-at-limit",
        ),
    ],
)
def test_when_the_request_is_on_its_limits_then_it_is_accepted(
    authenticated_client, install_chat_model, chat_url, limits
):
    """when the question and history sit exactly on their limits, 200 is returned.

    Validates app.api.schemas.chatbot.ChatRequest.
    """
    install_chat_model(FakeChatModel())

    assert authenticated_client.post(chat_url, json=limits).status_code == HTTPStatus.OK


def test_when_the_question_has_surrounding_whitespace_then_the_model_gets_it_trimmed(
    authenticated_client, install_chat_model, chat_url
):
    """when the question is padded with blanks, the model receives the stripped text.

    Validates app.api.schemas.chatbot.ChatRequest.
    """
    model = install_chat_model(FakeChatModel())

    authenticated_client.post(chat_url, json={"user_question": f"  {QUESTION}\n"})

    assert model.last_question == QUESTION


@pytest.mark.parametrize("route", CHAT_ROUTES)
def test_when_the_caller_is_unknown_then_authentication_is_checked_before_the_body(
    unauthenticated_client, api_prefix, route
):
    """when an unauthenticated caller sends an invalid body, the answer is 401, not 422.

    The router-level guard resolves the principal before the body is validated.

    Validates app.api.v1.endpoints.chatbot.router.
    """
    response = unauthenticated_client.post(
        f"{api_prefix}{route}", json={"user_question": ""}
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize("route", CHAT_ROUTES)
def test_when_there_is_no_principal_then_401_and_the_model_is_not_asked(
    unauthenticated_client, api_prefix, route
):
    """when no principal is resolved, both chat routes answer 401 without a model call.

    Every chat call is paid for at the provider, so it must not be anonymous.

    Validates app.api.v1.endpoints.chatbot.chat().
    """
    model = FakeChatModel()
    app.dependency_overrides[get_chat_model] = lambda: model

    response = unauthenticated_client.post(
        f"{api_prefix}{route}", json={"user_question": QUESTION}
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"
    assert model.last_question is None


def test_when_a_reply_is_streamed_then_partials_precede_one_terminal_done_event(
    authenticated_client, install_chat_model, stream_url
):
    """when a reply is streamed, partial events come first and one final event ends it.

    The final event holds the complete reply.

    Validates app.api.v1.endpoints.chatbot.chat_stream().
    """
    install_chat_model(FakeChatModel(answer="Hello", partials=("Hel", "lo")))

    response = authenticated_client.post(stream_url, json={"user_question": QUESTION})

    assert response.status_code == HTTPStatus.OK
    assert response.headers["content-type"].startswith(SSE_MEDIA_TYPE)
    assert server_events(response) == [
        {"content": "Hel", "done": False},
        {"content": "lo", "done": False},
        {"content": "Hello", "done": True},
    ]


def test_when_a_reply_is_streamed_then_proxies_are_told_not_to_buffer_it(
    authenticated_client, install_chat_model, stream_url
):
    """when the stream starts, the headers disable caching and proxy buffering.

    Validates app.api.v1.endpoints.chatbot.chat_stream().
    """
    install_chat_model(FakeChatModel())

    headers = authenticated_client.post(
        stream_url, json={"user_question": QUESTION}
    ).headers

    assert headers["cache-control"] == "no-cache"
    assert headers["x-accel-buffering"] == "no"


def test_when_a_stream_has_history_then_the_model_receives_it(
    authenticated_client, install_chat_model, stream_url
):
    """when the stream request carries history, the model sees the typed turns.

    Validates app.api.v1.endpoints.chatbot.chat_stream().
    """
    model = install_chat_model(FakeChatModel())

    authenticated_client.post(
        stream_url,
        json={
            "user_question": QUESTION,
            "conversation_history": {"messages": ["user: hi"]},
        },
    )

    assert list(model.last_history) == [ChatMessage(ChatRole.USER, "hi")]


def test_when_the_model_is_down_before_the_first_token_then_the_stream_answers_503(
    authenticated_client, install_chat_model, stream_url
):
    """when the outage precedes any output, the stream route answers a plain 503.

    The first chunk is read before the response starts, so the failure goes
    through the exception handler instead of becoming a 200 with an error body.

    Validates app.api.v1.endpoints.chatbot.chat_stream().
    """
    failure = ExternalServiceError(log_context={"provider": PROVIDER_DETAIL})
    install_chat_model(FakeChatModel(error=failure))

    response = authenticated_client.post(stream_url, json={"user_question": QUESTION})

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == OUTAGE_ERROR_CODE
    assert RETRY_AFTER_HEADER in response.headers
    assert PROVIDER_DETAIL not in response.text


def test_when_the_model_crashes_before_the_first_token_then_the_stream_answers_500(
    authenticated_client, install_chat_model, stream_url
):
    """when an unexpected error precedes any output, the stream route answers a 500.

    Validates app.api.v1.endpoints.chatbot.chat_stream().
    """
    install_chat_model(FakeChatModel(error=RuntimeError(PROVIDER_DETAIL)))

    response = authenticated_client.post(stream_url, json={"user_question": QUESTION})

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert PROVIDER_DETAIL not in response.text


def test_when_the_outage_comes_after_the_first_token_then_a_failure_event_ends_it(
    authenticated_client, install_chat_model, stream_url, caplog
):
    """when the provider fails midway, the stream ends with an event carrying its code.

    The status line is already sent, so the failure can only travel as an event.
    The expected kind of failure is logged once with its code and no traceback.

    Validates app.api.v1.endpoints.chatbot.chat_stream().
    """
    failure = ExternalServiceError(log_context={"provider": PROVIDER_DETAIL})
    install_chat_model(FailsAfterFirstPartial(failure))

    with caplog.at_level(logging.INFO, logger=STREAM_LOGGER):
        response = authenticated_client.post(
            stream_url, json={"user_question": QUESTION}
        )

    assert response.status_code == HTTPStatus.OK
    assert server_events(response) == [
        {"content": FIRST_PARTIAL, "done": False},
        {
            "content": STREAM_FAILURE_MESSAGE,
            "done": True,
            "error_code": OUTAGE_ERROR_CODE,
        },
    ]
    assert PROVIDER_DETAIL not in response.text
    (record,) = [item for item in caplog.records if item.name == STREAM_LOGGER]
    assert record.getMessage() == STREAM_FAILED_LOG_MESSAGE
    assert record.levelno == logging.ERROR
    assert record.error_code == OUTAGE_ERROR_CODE
    assert record.exc_info is None


def test_when_the_model_crashes_after_the_first_token_then_the_failure_event_is_generic(
    authenticated_client, install_chat_model, stream_url, caplog
):
    """when an unexpected error interrupts the stream, the final event is generic.

    The traceback is logged once, in the ``chat.stream_failed`` record.

    Validates app.api.v1.endpoints.chatbot.chat_stream().
    """
    crash = RuntimeError(PROVIDER_DETAIL)
    install_chat_model(FailsAfterFirstPartial(crash))

    with caplog.at_level(logging.INFO, logger=STREAM_LOGGER):
        response = authenticated_client.post(
            stream_url, json={"user_question": QUESTION}
        )

    assert server_events(response)[-1] == {
        "content": STREAM_FAILURE_MESSAGE,
        "done": True,
        "error_code": INTERNAL_ERROR_CODE,
    }
    assert PROVIDER_DETAIL not in response.text
    (record,) = [item for item in caplog.records if item.name == STREAM_LOGGER]
    assert record.getMessage() == STREAM_FAILED_LOG_MESSAGE
    assert record.exc_info[1] is crash


def test_when_the_model_produces_nothing_then_the_stream_is_empty_and_200(
    authenticated_client, install_chat_model, stream_url
):
    """when the model ends its stream without a chunk, the body is empty.

    Validates app.api.v1.endpoints.chatbot.chat_stream().
    """
    install_chat_model(SilentModel())

    response = authenticated_client.post(stream_url, json={"user_question": QUESTION})

    assert response.status_code == HTTPStatus.OK
    assert response.text == ""


def test_when_the_stream_request_is_invalid_then_a_json_422_is_returned(
    authenticated_client, install_chat_model, stream_url
):
    """when the stream body is invalid, a normal 422 envelope is returned, not a stream.

    Validates app.api.schemas.chatbot.ChatRequest.
    """
    install_chat_model(FakeChatModel())

    response = authenticated_client.post(stream_url, json={"user_question": ""})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.headers["content-type"].startswith("application/json")


def test_when_the_chat_model_is_requested_twice_then_one_port_instance_is_reused():
    """when the composition root is asked twice, it returns one cached chat model.

    The BAML client is stateless and costly to build, so it is built once.

    Validates app.api.deps.get_chat_model().
    """
    get_chat_model.cache_clear()
    try:
        first = get_chat_model()

        assert get_chat_model() is first
    finally:
        get_chat_model.cache_clear()


async def test_when_the_chatbot_service_is_built_then_it_wraps_the_given_model():
    """when the service is built from a model, it asks that model for replies.

    Validates app.api.deps.get_chatbot_service().
    """
    model = FakeChatModel(answer="from the fake")
    service = get_chatbot_service(model)

    answer = await service.answer(ChatQuery(question=QUESTION))

    assert answer.answer == "from the fake"
    assert model.last_question == QUESTION
