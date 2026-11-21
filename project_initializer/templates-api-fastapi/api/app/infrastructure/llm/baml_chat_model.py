"""BAML-backed implementation of the chat model port.

This is the only module that touches the generated ``baml_client`` for chat, so
the application layer depends on ``ChatModelPort`` and never on BAML types.
"""

import os
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import contextmanager

from baml_py.errors import BamlError

from app.domain.entities.chat import ChatMessage, ChatReplyChunk
from app.domain.exceptions import ExternalServiceError
from app.domain.ports.chat_model import ChatModelPort
from baml_client.async_client import BamlAsyncClient
from baml_client.async_client import b as default_baml_client
from baml_client.types import ChatTurn

BAML_LOG_ENVIRONMENT_VARIABLE = "BAML_LOG"
BAML_LOG_OFF = "off"

# The only error attributes that hold configuration or a status, never text that
# came from the prompt or from the provider's reply.
_SAFE_ERROR_ATTRIBUTES = ("client_name", "status_code", "finish_reason")


def _default_baml_logging_to_off() -> None:
    # At its default level BAML prints every prompt, the history and the raw reply
    # to stdout, and at WARN it prints them again with the provider's error body
    # when a call fails: unstructured multi-line text outside the JSON formatter
    # that carries user content. BAML reads BAML_LOG on each call, so an operator
    # who sets it (to debug a prompt, say) still wins over this default.
    os.environ.setdefault(BAML_LOG_ENVIRONMENT_VARIABLE, BAML_LOG_OFF)


def _failure_context(operation: str, error: BamlError) -> dict[str, object]:
    context: dict[str, object] = {
        "operation": operation,
        "error_type": type(error).__name__,
    }
    for attribute in _SAFE_ERROR_ATTRIBUTES:
        value = getattr(error, attribute, None)
        if isinstance(value, str | int):
            context[attribute] = value
    return context


@contextmanager
def _translate_provider_errors(operation: str) -> Iterator[None]:
    # BAML errors embed the prompt and the provider's raw reply in their text, so
    # neither the message nor the chained traceback may reach a log or a client.
    # The cause is dropped (``from None``) and only safe attributes are kept; the
    # handler that receives the ExternalServiceError logs it once.
    try:
        yield
    except BamlError as error:
        raise ExternalServiceError(
            log_context=_failure_context(operation, error)
        ) from None


def _to_turns(history: Sequence[ChatMessage]) -> list[ChatTurn]:
    return [
        ChatTurn(role=message.role.value, content=message.content)
        for message in history
    ]


class BamlChatModel(ChatModelPort):
    """Chat model that calls the ``Chat`` function defined in ``baml_src``.

    Args:
        client: BAML async client to call. Defaults to the generated singleton;
            tests pass a fake.
    """

    def __init__(self, client: BamlAsyncClient | None = None) -> None:
        _default_baml_logging_to_off()
        self._client = client if client is not None else default_baml_client

    async def complete(self, question: str, history: Sequence[ChatMessage]) -> str:
        """Produce the full reply in one call.

        Args:
            question: The user's latest message.
            history: Earlier turns, oldest first. May be empty.

        Returns:
            The complete reply text.

        Raises:
            ExternalServiceError: The provider failed or the reply could not be
                parsed. The provider's error text is dropped because it can embed
                the prompt; ``log_context`` keeps only the operation, the error
                type and, when present, the client name, HTTP status and finish
                reason. The adapter writes no log of its own.
        """
        turns = _to_turns(history)
        with _translate_provider_errors("complete"):
            response = await self._client.Chat(user_question=question, history=turns)
        return response.answer

    async def stream(
        self, question: str, history: Sequence[ChatMessage]
    ) -> AsyncIterator[ChatReplyChunk]:
        """Produce the reply incrementally.

        Args:
            question: The user's latest message.
            history: Earlier turns, oldest first. May be empty.

        Yields:
            Chunks whose content is the reply text accumulated so far, ending
            with one chunk marked ``is_final`` that carries the complete reply.

        Raises:
            ExternalServiceError: The provider failed or the reply could not be
                parsed. The provider's error text is dropped because it can embed
                the prompt; ``log_context`` keeps only the operation, the error
                type and, when present, the client name, HTTP status and finish
                reason. The adapter writes no log of its own.
        """
        turns = _to_turns(history)
        with _translate_provider_errors("stream"):
            baml_stream = self._client.stream.Chat(
                user_question=question, history=turns
            )
            async for partial in baml_stream:
                if partial.answer:
                    yield ChatReplyChunk(content=partial.answer, is_final=False)
            final = await baml_stream.get_final_response()
        yield ChatReplyChunk(content=final.answer, is_final=True)
